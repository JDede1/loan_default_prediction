from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import os
import requests
import json

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# -----------------------
# Config (Airflow Variables / .env)
# -----------------------
GCS_BUCKET = Variable.get("GCS_BUCKET", default_var=os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"))

TRAIN_DATA_PATH = Variable.get(
    "TRAIN_DATA_PATH",
    default_var=os.getenv("TRAIN_DATA_PATH", f"gs://{GCS_BUCKET}/data/loan_default_selected_features_clean.csv"),
)

# ✅ Latest predictions now tracked in Airflow Variable (set by batch_predict.py)
LATEST_PREDICTION_PATH = Variable.get("LATEST_PREDICTION_PATH", default_var="")

SLACK_WEBHOOK_URL = Variable.get("SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", ""))


# -----------------------
# Notifications
# -----------------------
def notify_slack(message: str):
    if not SLACK_WEBHOOK_URL:
        print("ℹ️ SLACK_WEBHOOK_URL not set; skipping Slack notification.")
        return
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"text": message}),
            timeout=10,
        )
        print(f"Slack response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"⚠️ Slack notification failed: {e}")


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

    # ✅ Directly use Airflow Variable instead of reading marker file
    bash_cmd = f"""
    if [ -z "{LATEST_PREDICTION_PATH}" ]; then
        echo "❌ ERROR: LATEST_PREDICTION_PATH Airflow Variable is not set"
        exit 1
    fi

    echo "📌 TRAIN_DATA_PATH={TRAIN_DATA_PATH}"
    echo "📌 LATEST_PREDICTION_PATH={LATEST_PREDICTION_PATH}"

    python /opt/airflow/src/monitor_predictions.py \
        --train_data_path "{TRAIN_DATA_PATH}" \
        --prediction_path "{LATEST_PREDICTION_PATH}"
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
            "MLFLOW_ARTIFACT_URI": os.getenv("MLFLOW_ARTIFACT_URI", f"gs://{GCS_BUCKET}/mlflow"),
            "GCS_BUCKET": GCS_BUCKET,
            "TRAIN_DATA_PATH": TRAIN_DATA_PATH,
            "LATEST_PREDICTION_PATH": LATEST_PREDICTION_PATH,
        },
        on_failure_callback=lambda context: notify_slack("❌ Monitoring DAG failed. Check Airflow logs."),
        on_success_callback=lambda context: notify_slack("✅ Monitoring DAG completed successfully."),
    )

    run_monitoring
