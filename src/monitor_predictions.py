import os
import json
import shutil
import pandas as pd
from datetime import datetime
from typing import List

from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.pipeline.column_mapping import ColumnMapping

# Phase 2 imports
from airflow.models import Variable
from google.cloud import storage

# =========================
# Paths & constants
# =========================
BASE_DIR = "/opt/airflow"
DATA_DIR = os.path.join(BASE_DIR, "data")
ARTIFACT_DIR = os.path.join(BASE_DIR, "artifacts")
TMP_ARTIFACT_DIR = "/tmp/artifacts"

TRAIN_DATA_PATH = os.path.join(DATA_DIR, "loan_default_selected_features_clean.csv")

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
        print(f"⚠️ Permission denied writing directly to {path}. Keeping in tmp: {tmp_name}")
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
    print("✅ Upload complete.")

# =========================
# Main
# =========================
def main():
    # Unique filenames per run
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_json_path = os.path.join(ARTIFACT_DIR, f"monitoring_report_{timestamp}.json")
    report_html_path = os.path.join(ARTIFACT_DIR, f"monitoring_report_{timestamp}.html")

    # Determine prediction path
    try:
        latest_pred_path = Variable.get("LATEST_PREDICTION_PATH", default_var="")
    except Exception:
        latest_pred_path = ""

    if latest_pred_path and os.path.exists(latest_pred_path):
        batch_file = latest_pred_path
        print(f"📌 Using prediction file from Airflow Variable: {batch_file}")
    else:
        print("🔎 Searching for latest batch prediction file...")
        batch_file = get_latest_prediction_file()

    # 1) Load training (reference) data
    print("📦 Loading training (reference) data...")
    train_df = pd.read_csv(TRAIN_DATA_PATH)
    print(f"✅ train_df: {train_df.shape[0]} rows, {train_df.shape[1]} cols")

    # 2) Load batch predictions
    batch_df = pd.read_csv(batch_file)
    print(f"✅ batch_df: {batch_df.shape[0]} rows, {batch_df.shape[1]} cols")

    # 3) Ensure target column alignment
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

    # 4) Column mapping for Evidently
    column_mapping = ColumnMapping()
    column_mapping.target = TARGET_COL

    # 5) Build & run Evidently report
    print("📊 Running Evidently drift report...")
    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(reference_data=train_df, current_data=batch_df, column_mapping=column_mapping)

    # 6) Save reports locally (safe write)
    json_text = json.dumps(report.as_dict(), indent=2)
    final_json_path = safe_write_text(report_json_path, json_text)

    html_str = report.get_html()
    html_bytes = html_str.encode("utf-8")
    final_html_path = safe_write_bytes(report_html_path, html_bytes)

    print("✅ Monitoring report saved:")
    print(f"   • JSON: {final_json_path}")
    print(f"   • HTML: {final_html_path}")
    print(f"🕒 Timestamp: {timestamp}")

    # 7) Optional: Upload to GCS
    storage_backend = os.getenv("STORAGE_BACKEND", "local")
    gcs_bucket = os.getenv("GCS_BUCKET")

    if storage_backend.lower() == "gcs" and gcs_bucket:
        upload_to_gcs(final_json_path, gcs_bucket, f"reports/{os.path.basename(final_json_path)}")
        upload_to_gcs(final_html_path, gcs_bucket, f"reports/{os.path.basename(final_html_path)}")

if __name__ == "__main__":
    main()
