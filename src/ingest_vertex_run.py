"""
Ingest Vertex AI training outputs from GCS into MLflow.
- Reads metrics.json and params.json from GCS
- Logs them into the central MLflow server
- Uploads model artifacts from GCS into MLflow registry
"""

import argparse
import json
import os
import tempfile

import mlflow
from google.cloud import storage
from mlflow.tracking import MlflowClient


def download_from_gcs(bucket_name: str, gcs_path: str, local_path: str):
    """Download a single file from GCS to local path."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    blob.download_to_filename(local_path)
    print(f"📥 Downloaded gs://{bucket_name}/{gcs_path} → {local_path}")
    return local_path


def main(args):
    gcs_bucket = args.gcs_bucket
    run_prefix = args.run_prefix.rstrip("/")  # e.g. vertex_runs/20250916_120000
    model_name = args.model_name
    alias = args.alias

    # Configure MLflow tracking
    mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    client = MlflowClient()

    # Temp local dir for downloads
    tmpdir = tempfile.mkdtemp()

    # --- Download metrics & params ---
    metrics_local = download_from_gcs(
        gcs_bucket,
        f"{run_prefix}/metrics.json",
        os.path.join(tmpdir, "metrics.json"),
    )
    params_local = download_from_gcs(
        gcs_bucket,
        f"{run_prefix}/params.json",
        os.path.join(tmpdir, "params.json"),
    )

    with open(metrics_local) as f:
        metrics = json.load(f)
    with open(params_local) as f:
        params = json.load(f)

    print(f"✅ Loaded metrics: {metrics}")
    print(f"✅ Loaded params: {params}")

    # --- Start new MLflow run ---
    experiment_name = "loan_default_experiment"

    # Ensure experiment has artifact location set (prefer env)
    # Fallback to bucket/mlflow if not provided
    mlflow_artifact_uri = os.getenv(
        "MLFLOW_ARTIFACT_URI",
        f"gs://{gcs_bucket}/mlflow",
    )

    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = client.create_experiment(
            experiment_name,
            artifact_location=mlflow_artifact_uri,
        )
        print(
            f"✅ Created experiment '{experiment_name}' "
            f"with artifact location {mlflow_artifact_uri}"
        )
    else:
        experiment_id = experiment.experiment_id
        print(
            f"ℹ️ Using existing experiment '{experiment_name}' "
            f"(artifact location: {experiment.artifact_location})"
        )

    with mlflow.start_run(experiment_id=experiment_id) as run:
        run_id = run.info.run_id
        print(f"🚀 Logging Vertex outputs into MLflow run {run_id}")
        print(
            "🏃 View run at: "
            f"{mlflow_tracking_uri}/#/experiments/{experiment_id}/runs/{run_id}"
        )

        mlflow.log_metrics(metrics)
        mlflow.log_params(params)

        # --- Download model folder from GCS ---
        local_model_dir = os.path.join(tmpdir, "model")
        os.makedirs(local_model_dir, exist_ok=True)

        client_gcs = storage.Client()
        bucket = client_gcs.bucket(gcs_bucket)
        blobs = list(bucket.list_blobs(prefix=f"{run_prefix}/model/"))

        for blob in blobs:
            rel_path = blob.name.replace(f"{run_prefix}/model/", "")
            if not rel_path:  # skip directory placeholders
                continue
            local_file = os.path.join(local_model_dir, rel_path)
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            blob.download_to_filename(local_file)

        # --- Log entire model directory as artifacts ---
        mlflow.log_artifacts(local_model_dir, artifact_path="model")

        # --- Ensure registered model exists ---
        try:
            client.get_registered_model(model_name)
            print(f"ℹ️ Registered model '{model_name}' already exists.")
        except Exception:
            client.create_registered_model(model_name)
            print(f"✅ Created registered model '{model_name}'")

        # --- Register model version ---
        model_uri = f"runs:/{run_id}/model"
        mv = client.create_model_version(
            name=model_name,
            source=model_uri,
            run_id=run_id,
        )
        print(f"✅ Registered model {model_name} v{mv.version}")

        # --- Assign alias ---
        if alias:
            client.set_registered_model_alias(
                name=model_name,
                alias=alias.lower(),
                version=mv.version,
            )
            print(f"✅ Assigned alias '{alias}' to version {mv.version}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Vertex AI outputs into MLflow")
    parser.add_argument("--gcs_bucket", required=True, help="GCS bucket name")
    parser.add_argument(
        "--run_prefix",
        required=True,
        help="Run prefix path in bucket (e.g. vertex_runs/20250916_120000)",
    )
    parser.add_argument("--model_name", default="loan_default_model")
    parser.add_argument("--alias", default="staging")
    args = parser.parse_args()

    main(args)
