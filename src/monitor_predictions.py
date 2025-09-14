import argparse
import json
import os
import shutil
from datetime import datetime
from typing import List

import pandas as pd
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.pipeline.column_mapping import ColumnMapping
from evidently.report import Report

# Phase 2 imports
try:
    from airflow.models import Variable
except ImportError:
    Variable = None  # Allow running outside Airflow

from google.cloud import storage


# =========================
# Paths & constants
# =========================
BASE_DIR = "/opt/airflow"
ARTIFACT_DIR = os.path.join(BASE_DIR, "artifacts")
TMP_ARTIFACT_DIR = "/tmp/artifacts"

# Ensure dirs exist
os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(TMP_ARTIFACT_DIR, exist_ok=True)


# =========================
# Helpers
# =========================
def list_prediction_files(directories: List[str]) -> List[str]:
    """Return a sorted (newest-first) list of predictions_*.csv across given directories."""
    found = []
    for d in directories:
        try:
            for f in os.listdir(d):
                if f.startswith("predictions_") and f.endswith(".csv"):
                    found.append(os.path.join(d, f))
        except FileNotFoundError:
            continue
    return sorted(found, reverse=True)


def get_latest_prediction_file() -> str:
    """Find the newest predictions file from artifacts or tmp."""
    candidates = list_prediction_files([ARTIFACT_DIR, TMP_ARTIFACT_DIR])
    if not candidates:
        raise FileNotFoundError(
            f"❌ No batch prediction files found in {ARTIFACT_DIR} or {TMP_ARTIFACT_DIR}."
        )
    latest = candidates[0]
    print(f"✅ Using latest batch predictions: {latest}")
    return latest


def safe_write_bytes(path: str, data: bytes) -> str:
    """Try writing to ARTIFACT_DIR first, fallback to TMP if permissions fail."""
    tmp_name = os.path.join(TMP_ARTIFACT_DIR, f"tmp_{os.path.basename(path)}")
    with open(tmp_name, "wb") as f:
        f.write(data)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(tmp_name, path)
        return path
    except PermissionError:
        print(f"⚠️ Permission denied writing {path}. Keeping in tmp: {tmp_name}")
        return tmp_name


def safe_write_text(path: str, text: str) -> str:
    return safe_write_bytes(path, text.encode("utf-8"))


def upload_to_gcs(local_path: str, bucket_name: str, destination_blob: str):
    """Upload a file to GCS."""
    print(f"📤 Uploading {local_path} to gs://{bucket_name}/{destination_blob}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(local_path)
    print(f"✅ Upload complete → gs://{bucket_name}/{destination_blob}")


def read_csv_maybe_gcs(path: str) -> pd.DataFrame:
    """Read CSV from local path or gs:// URI."""
    if path.startswith("gs://"):
        return pd.read_csv(path, storage_options={"token": "google_default"})
    return pd.read_csv(path)


def notify_slack(message: str):
    """Send a message to Slack if webhook is configured."""
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        return
    try:
        import requests
        requests.post(url, headers={"Content-Type": "application/json"},
                      data=json.dumps({"text": message}), timeout=10)
    except Exception as e:
        print(f"⚠️ Slack notify failed: {e}")


# =========================
# Main
# =========================
def main(args):
    # --------------------
    # Resolve input paths
    # --------------------
    train_data_path = args.train_data_path or os.getenv("TRAIN_DATA_PATH")
    prediction_path = args.prediction_path

    # Fallback to Airflow Variables if needed
    if not train_data_path and Variable:
        try:
            train_data_path = Variable.get("TRAIN_DATA_PATH", default_var="")
        except Exception:
            train_data_path = ""

    if not prediction_path and Variable:
        try:
            prediction_path = Variable.get("LATEST_PREDICTION_PATH", default_var="")
        except Exception:
            prediction_path = ""

    if not prediction_path:
        print("🔎 Searching for latest batch prediction file...")
        prediction_path = get_latest_prediction_file()

    if not train_data_path or not prediction_path:
        msg = (f"❌ Missing paths: TRAIN_DATA_PATH={train_data_path}, "
               f"PREDICTION_PATH={prediction_path}")
        notify_slack(msg)
        raise ValueError(msg)

    print(f"📌 TRAIN_DATA_PATH={train_data_path}")
    print(f"📌 PREDICTION_PATH={prediction_path}")

    # --------------------
    # File naming
    # --------------------
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_json_path = os.path.join(ARTIFACT_DIR, f"monitoring_report_{timestamp}.json")
    report_html_path = os.path.join(ARTIFACT_DIR, f"monitoring_report_{timestamp}.html")

    # --------------------
    # Load datasets
    # --------------------
    print("📦 Loading training (reference) data...")
    train_df = read_csv_maybe_gcs(train_data_path)
    print(f"✅ train_df: {train_df.shape[0]} rows, {train_df.shape[1]} cols")

    print("📦 Loading batch predictions...")
    batch_df = read_csv_maybe_gcs(prediction_path)
    print(f"✅ batch_df: {batch_df.shape[0]} rows, {batch_df.shape[1]} cols")

    # --------------------
    # Align columns
    # --------------------
    TARGET_COL = "loan_status"
    if "prediction" in train_df.columns:
        train_df = train_df.drop(columns=["prediction"])
    if TARGET_COL not in batch_df.columns:
        print(f"⚠️ '{TARGET_COL}' not found in batch_df — adding dummy zeros.")
        batch_df[TARGET_COL] = 0

    common_cols = [c for c in train_df.columns if c in batch_df.columns]
    if TARGET_COL in train_df.columns and TARGET_COL not in common_cols:
        common_cols.append(TARGET_COL)

    train_df = train_df[common_cols]
    batch_df = batch_df[common_cols]
    print(f"✅ Aligned on {len(common_cols)} columns")

    # --------------------
    # Run Evidently
    # --------------------
    print("📊 Running Evidently drift report...")
    column_mapping = ColumnMapping()
    column_mapping.target = TARGET_COL

    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(reference_data=train_df, current_data=batch_df,
               column_mapping=column_mapping)

    # --------------------
    # Save reports
    # --------------------
    json_text = json.dumps(report.as_dict(), indent=2)
    final_json_path = safe_write_text(report_json_path, json_text)

    html_str = report.get_html()
    html_bytes = html_str.encode("utf-8")
    final_html_path = safe_write_bytes(report_html_path, html_bytes)

    print("✅ Monitoring report saved:")
    print(f"   • JSON: {final_json_path}")
    print(f"   • HTML: {final_html_path}")
    print(f"🕒 Timestamp: {timestamp}")

    # --------------------
    # Upload to GCS if enabled
    # --------------------
    storage_backend = os.getenv("STORAGE_BACKEND", "local")
    gcs_bucket = os.getenv("GCS_BUCKET")

    if storage_backend.lower() == "gcs" and gcs_bucket:
        dest_json = f"reports/{os.path.basename(final_json_path)}"
        dest_html = f"reports/{os.path.basename(final_html_path)}"
        upload_to_gcs(final_json_path, gcs_bucket, dest_json)
        upload_to_gcs(final_html_path, gcs_bucket, dest_html)

    # --------------------
    # Optional: Log to MLflow
    # --------------------
    try:
        import mlflow
        mlflow.log_dict(report.as_dict(), "monitoring/report.json")
        print("✅ Monitoring report also logged to MLflow")
    except Exception as e:
        print(f"⚠️ Skipped MLflow logging: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Evidently monitoring on training vs prediction data"
    )
    parser.add_argument("--train_data_path", type=str,
                        help="Path to training data (CSV). Supports gs:// paths.")
    parser.add_argument("--prediction_path", type=str,
                        help="Path to prediction data (CSV). Supports gs:// paths.")
    args = parser.parse_args()

    main(args)
