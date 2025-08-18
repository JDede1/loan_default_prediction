from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
import os

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# -----------------------
# Config
# -----------------------
TRAIN_DATA_PATH = os.getenv(
    "TRAIN_DATA_PATH",
    "gs://loan-default-artifacts-loan-default-mlops/data/loan_default_selected_features_clean.csv",
)

# ✅ Marker file created by batch_prediction_dag
LATEST_MARKER_PATH = "gs://loan-default-artifacts-loan-default-mlops/predictions/latest_prediction.txt"

# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="monitoring_dag",
    default_args=default_args,
    description="Daily monitoring with Evidently using latest predictions",
    start_date=datetime(2025, 8, 1),
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["monitoring", "evidently"],
) as dag:

    # ✅ Authenticate + resolve latest prediction dynamically
    bash_cmd = f"""
    gcloud auth activate-service-account --key-file=/opt/airflow/keys/gcs-service-account.json
    LATEST_PREDICTION_PATH=$(gsutil cat {LATEST_MARKER_PATH} || echo "")
    if [ -z "$LATEST_PREDICTION_PATH" ]; then
        echo "❌ ERROR: latest_prediction.txt is empty or missing"
        exit 1
    else
        echo "📌 TRAIN_DATA_PATH={TRAIN_DATA_PATH}"
        echo "📌 LATEST_PREDICTION_PATH=$LATEST_PREDICTION_PATH"
        python /opt/airflow/src/monitor_predictions.py \
            --train_data_path "{TRAIN_DATA_PATH}" \
            --prediction_path "$LATEST_PREDICTION_PATH"
    fi
    """

    run_monitoring = BashOperator(
        task_id="run_monitor_predictions",
        bash_command=bash_cmd,
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
            "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
            "MLFLOW_ARTIFACT_URI": os.getenv(
                "MLFLOW_ARTIFACT_URI",
                f"gs://{os.getenv('GCS_BUCKET', 'loan-default-artifacts-loan-default-mlops')}/mlflow",
            ),
            "GCS_BUCKET": os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"),
            "TRAIN_DATA_PATH": TRAIN_DATA_PATH,
        },
    )

    run_monitoring
