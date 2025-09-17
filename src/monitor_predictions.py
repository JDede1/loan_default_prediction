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

try:
    from airflow.models import Variable
except ImportError:
    Variable = None

from google.cloud import storage

# =========================
# Paths & constants
# =========================
BASE_DIR = "/opt/airflow"
ARTIFACT_DIR = os.path.join(BASE_DIR, "artifacts")
TMP_ARTIFACT_DIR = "/tmp/artifacts"

os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(TMP_ARTIFACT_DIR, exist_ok=True)


# =========================
# Helpers
# =========================
def list_prediction_files(directories: List[str]) -> List[str]:
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
    candidates = list_prediction_files([ARTIFACT_DIR, TMP_ARTIFACT_DIR])
    if not candidates:
        raise FileNotFoundError(
            "❌ No batch prediction files found in "
            f"{ARTIFACT_DIR} or {TMP_ARTIFACT_DIR}."
        )
    latest = candidates[0]
    print(f"✅ Using latest batch predictions: {latest}")
    return latest


def safe_write_bytes(path: str, data: bytes) -> str:
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
    print(f"📤 Uploading {local_path} to gs://{bucket_name}/{destination_blob}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(local_path)
    print(f"✅ Upload complete → gs://{bucket_name}/{destination_blob}")


def read_csv_maybe_gcs(path: str) -> pd.DataFrame:
    if path.startswith("gs://"):
        return pd.read_csv(path, storage_options={"token": "google_default"})
    return pd.read_csv(path)


def notify_slack(message: str):
    url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        return
    try:
        import requests

        requests.post(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"text": message}),
            timeout=10,
        )
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
        msg = (
            f"❌ Missing paths: TRAIN_DATA_PATH={train_data_path}, "
            f"PREDICTION_PATH={prediction_path}"
        )
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

    # --------------------
    # Run Evidently
    # --------------------
    print("📊 Running Evidently drift report...")
    column_mapping = ColumnMapping()
    column_mapping.target = TARGET_COL

    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(
        reference_data=train_df, current_data=batch_df, column_mapping=column_mapping
    )

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
    # Drift Threshold Check
    # --------------------
    drift_share = (
        report.as_dict().get("metrics", [])[0].get("result", {}).get("drift_share", 0)
    )
    threshold = float(
        os.getenv(
            "DRIFT_THRESHOLD",
            Variable.get("DRIFT_THRESHOLD", default_var="0.3") if Variable else 0.3,
        )
    )
    drift_detected = drift_share > threshold

    msg = (
        f"📊 Drift share={drift_share:.2f}, "
        f"threshold={threshold:.2f} → drift={drift_detected}"
    )
    notify_slack(msg)
    print(msg)

    # --------------------
    # Save drift decision JSON if requested
    # --------------------
    if args.status_out:
        status = {
            "drift": drift_detected,
            "drift_share": drift_share,
            "threshold": threshold,
        }
        with open(args.status_out, "w") as f:
            json.dump(status, f, indent=2)
        print(f"📝 Drift status written to {args.status_out}: {status}")

        # ✅ Also store path in Airflow Variable for visibility
        if Variable:
            try:
                Variable.set("LATEST_DRIFT_REPORT_PATH", args.status_out)
                print(
                    "📌 Airflow Variable LATEST_DRIFT_REPORT_PATH "
                    f"set to: {args.status_out}"
                )
            except Exception as e:
                print(f"⚠️ Could not set Airflow Variable: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Evidently monitoring on training vs prediction data"
    )
    parser.add_argument(
        "--train_data_path",
        type=str,
        help="Path to training data (CSV). Supports gs:// paths.",
    )
    parser.add_argument(
        "--prediction_path",
        type=str,
        help="Path to prediction data (CSV). Supports gs:// paths.",
    )
    parser.add_argument(
        "--status_out",
        type=str,
        default=None,
        help="Optional path to save drift decision JSON",
    )
    args = parser.parse_args()

    main(args)
