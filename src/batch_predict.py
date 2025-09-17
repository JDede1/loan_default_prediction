import argparse
import json
import os
import shutil
from datetime import datetime

import mlflow.pyfunc
import pandas as pd

# Phase 2 imports
try:
    from airflow.models import Variable
except ImportError:
    Variable = None  # Allow running outside Airflow

from google.cloud import storage

# -----------------------
# Constants
# -----------------------
BASE_DIR = "/opt/airflow"
ARTIFACT_DIR = os.path.join(BASE_DIR, "artifacts")
TMP_ARTIFACT_DIR = "/tmp/artifacts"  # Always writable

# Ensure dirs exist
os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(TMP_ARTIFACT_DIR, exist_ok=True)


# -----------------------
# Safe file write helper
# -----------------------
def safe_write_csv(df: pd.DataFrame, final_path: str) -> str:
    """
    Writes CSV to tmp first, then moves to final path if possible.
    Returns the path where the file actually ended up.
    """
    tmp_path = os.path.join(TMP_ARTIFACT_DIR, os.path.basename(final_path))
    df.to_csv(tmp_path, index=False)

    try:
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        shutil.copy2(tmp_path, final_path)
        return final_path
    except PermissionError:
        print(f"⚠️ Permission denied writing to {final_path}, using tmp instead.")
        return tmp_path


# -----------------------
# GCS Upload helper
# -----------------------
def upload_to_gcs(local_path: str, bucket_name: str, destination_blob: str):
    print(f"📤 Uploading {local_path} to gs://{bucket_name}/{destination_blob}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(local_path)
    print("✅ Upload complete.")


# -----------------------
# Main
# -----------------------
def main(args):
    print("\n📌 Running batch prediction with settings:")
    print(f"Model name: {args.model_name}")
    print(f"Alias: {args.alias}")
    print(f"Input path: {args.input_path}")
    print(f"Output path (base): {args.output_path}")

    # ---------------------------
    # 1. Load model from MLflow Registry
    # ---------------------------
    model_uri = f"models:/{args.model_name}@{args.alias}"
    print(f"\n📥 Loading model from MLflow Registry: {model_uri}")
    model = mlflow.pyfunc.load_model(model_uri)
    print("✅ Model loaded successfully!")

    # ---------------------------
    # 2. Load input data (local or GCS)
    # ---------------------------
    print(f"\n📥 Reading batch input from: {args.input_path}")
    if args.input_path.startswith("gs://"):
        # GCS input handled by pandas + gcsfs
        df = pd.read_csv(args.input_path)
    else:
        ext = os.path.splitext(args.input_path)[-1].lower()
        if ext == ".csv":
            df = pd.read_csv(args.input_path)
        elif ext == ".json":
            df = pd.read_json(args.input_path)
        elif ext == ".parquet":
            df = pd.read_parquet(args.input_path)
        else:
            raise ValueError("❌ Unsupported file format. Use CSV, JSON, or Parquet.")

    print(f"📊 Input data shape: {df.shape}")

    # ---------------------------
    # 3. Run predictions
    # ---------------------------
    print("\n⚙️ Generating predictions...")
    preds = model.predict(df)

    # ---------------------------
    # 4. Save predictions with timestamp
    # ---------------------------
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    base_name = os.path.basename(args.output_path).replace(".csv", "")
    output_file = f"{base_name}_{timestamp}.csv"
    final_output_path = os.path.join(os.path.dirname(args.output_path), output_file)

    df_output = df.copy()
    df_output["prediction"] = preds
    saved_path = safe_write_csv(df_output, final_output_path)

    print(f"✅ Predictions saved locally: {saved_path}")

    # ---------------------------
    # 5. Upload to GCS (always if bucket is set)
    # ---------------------------
    gcs_bucket = os.getenv("GCS_BUCKET")
    if gcs_bucket:
        gcs_destination = f"predictions/{os.path.basename(saved_path)}"
        upload_to_gcs(saved_path, gcs_bucket, gcs_destination)
        saved_path = f"gs://{gcs_bucket}/{gcs_destination}"
        print(f"✅ Predictions also available in GCS: {saved_path}")

    # ---------------------------
    # 6. Store latest prediction path in Airflow Variable
    # ---------------------------
    if Variable:
        try:
            Variable.set("LATEST_PREDICTION_PATH", saved_path)
            print(f"📌 Airflow Variable LATEST_PREDICTION_PATH set to: {saved_path}")
        except Exception as e:
            print(f"⚠️ Could not set Airflow Variable: {e}")
    else:
        print("ℹ️ Not running inside Airflow — skipping Variable.set()")

    # ---------------------------
    # 7. Write marker file (always as fallback)
    # ---------------------------
    marker_file = os.path.join(ARTIFACT_DIR, "latest_prediction.json")
    marker_data = {
        "LATEST_PREDICTION_PATH": saved_path,
        "created_at": datetime.now().isoformat(),
        "model_name": args.model_name,
        "alias": args.alias,
    }
    try:
        with open(marker_file, "w") as f:
            json.dump(marker_data, f, indent=2)
        print(f"📌 Marker file written: {marker_file}")
    except Exception as e:
        print(f"⚠️ Could not write marker file: {e}")

    # ---------------------------
    # 8. Summary
    # ---------------------------
    print(f"\n📌 Batch prediction completed for {len(df)} records.")
    print(f"📁 Final output file: {saved_path}")
    print(f"🕒 Timestamp: {datetime.now().isoformat()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch prediction using MLflow model registry"
    )
    parser.add_argument(
        "--model_name",
        default="loan_default_model",
        help="Name of the registered MLflow model",
    )
    parser.add_argument(
        "--alias", default="staging", help="Model alias to load from registry"
    )
    parser.add_argument(
        "--input_path",
        default=os.getenv("PREDICTION_INPUT_PATH", "data/batch_input.csv"),
        help="Input file path (CSV, JSON, Parquet). Supports gs:// paths.",
    )
    parser.add_argument(
        "--output_path",
        default=os.getenv("PREDICTION_OUTPUT_PATH", "artifacts/predictions.csv"),
        help="Base path for output file (timestamp will be added).",
    )
    args = parser.parse_args()

    main(args)
