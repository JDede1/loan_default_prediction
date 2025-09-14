from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from datetime import datetime, timedelta
import os
import requests

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

# -----------------------
# Config (Airflow Variables / .env)
# -----------------------
MODEL_NAME = Variable.get("MODEL_NAME", default_var=os.getenv("MODEL_NAME", "loan_default_model"))
MODEL_ALIAS = Variable.get("MODEL_ALIAS", default_var=os.getenv("MODEL_ALIAS", "staging"))

GCS_BUCKET = Variable.get("GCS_BUCKET", default_var=os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"))

PREDICTION_INPUT_PATH = Variable.get(
    "PREDICTION_INPUT_PATH",
    default_var=os.getenv("PREDICTION_INPUT_PATH", f"gs://{GCS_BUCKET}/data/batch_input.csv"),
)

PREDICTION_OUTPUT_PATH = Variable.get(
    "PREDICTION_OUTPUT_PATH",
    default_var=os.getenv("PREDICTION_OUTPUT_PATH", f"gs://{GCS_BUCKET}/predictions/predictions.csv"),
)

SLACK_WEBHOOK_URL = Variable.get("SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", ""))


# -----------------------
# Notifications
# -----------------------
def notify_slack(message: str):
    if SLACK_WEBHOOK_URL:
        try:
            requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
        except Exception as e:
            print(f"⚠️ Slack notification failed: {e}")


# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="batch_prediction_dag",
    default_args=default_args,
    description="Batch loan default prediction using registered MLflow model",
    schedule_interval="@daily",
    start_date=datetime(2025, 8, 1),
    catchup=False,
    max_active_runs=1,
    tags=["batch", "prediction", "mlflow"],
) as dag:

    # 1️⃣ Run batch predictions (script handles timestamp, GCS upload, and LATEST_PREDICTION_PATH)
    run_batch_prediction = BashOperator(
        task_id="run_batch_prediction",
        bash_command=(
            f"echo '🚀 Running batch prediction with model={MODEL_NAME}, alias={MODEL_ALIAS}' && "
            f"python /opt/airflow/src/batch_predict.py "
            f"--model_name {MODEL_NAME} "
            f"--alias {MODEL_ALIAS} "
            f"--input_path {PREDICTION_INPUT_PATH} "
            f"--output_path {PREDICTION_OUTPUT_PATH}"
        ),
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
            "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
            "MLFLOW_ARTIFACT_URI": os.getenv("MLFLOW_ARTIFACT_URI", f"gs://{GCS_BUCKET}/mlflow"),
            "GCS_BUCKET": GCS_BUCKET,
            "PREDICTION_INPUT_PATH": PREDICTION_INPUT_PATH,
            "PREDICTION_OUTPUT_PATH": PREDICTION_OUTPUT_PATH,
            "STORAGE_BACKEND": "gcs",  # ✅ ensures predictions go to GCS
        },
        on_failure_callback=lambda context: notify_slack("❌ Batch prediction failed."),
    )

    # 2️⃣ Trigger monitoring DAG after predictions
    trigger_monitoring = TriggerDagRunOperator(
        task_id="trigger_monitoring",
        trigger_dag_id="monitoring_dag",
        wait_for_completion=False,
    )

    # DAG flow
    run_batch_prediction >> trigger_monitoring
