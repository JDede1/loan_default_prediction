from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
import os
import requests
import json

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

# -----------------------
# Config
# -----------------------
GCS_BUCKET = Variable.get(
    "GCS_BUCKET",
    default_var=os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"),
)

TRAIN_DATA_PATH = Variable.get(
    "TRAIN_DATA_PATH",
    default_var=os.getenv(
        "TRAIN_DATA_PATH",
        f"gs://{GCS_BUCKET}/data/loan_default_selected_features_clean.csv",
    ),
)

MARKER_FILE = "/opt/airflow/artifacts/latest_prediction.json"
SLACK_WEBHOOK_URL = Variable.get(
    "SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", "")
)

DRIFT_STATUS_FILE = "/opt/airflow/artifacts/drift_status.json"  # written by monitor_predictions.py

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
# Resolve latest prediction path
# -----------------------
def resolve_latest_prediction(**context):
    path = ""
    try:
        path = Variable.get("LATEST_PREDICTION_PATH", default_var="")
    except Exception:
        path = ""

    if not path and os.path.exists(MARKER_FILE):
        try:
            with open(MARKER_FILE, "r") as f:
                marker = json.load(f)
                path = marker.get("LATEST_PREDICTION_PATH", "")
                print(f"📌 Loaded LATEST_PREDICTION_PATH from marker file: {path}")
        except Exception as e:
            print(f"⚠️ Failed to read marker file: {e}")

    if not path:
        raise ValueError("❌ No predictions found. Run batch_prediction_dag first.")

    print(f"📌 Resolved prediction path: {path}")
    context["ti"].xcom_push(key="prediction_path", value=path)


# -----------------------
# Branch: check drift
# -----------------------
def check_drift():
    if not os.path.exists(DRIFT_STATUS_FILE):
        print("⚠️ Drift status file not found. Skipping retrain.")
        return "no_drift"

    with open(DRIFT_STATUS_FILE, "r") as f:
        status = json.load(f)

    drift_detected = status.get("drift", False)
    print(f"📊 Drift detected? {drift_detected}")

    if drift_detected:
        notify_slack("⚠️ Data drift detected! Triggering retraining pipeline...")
        return "trigger_retrain"
    else:
        notify_slack("✅ No significant drift detected. Skipping retraining.")
        return "no_drift"


# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="monitoring_dag",
    default_args=default_args,
    description="Daily monitoring with Evidently + auto-retraining trigger",
    start_date=datetime(2025, 8, 1),
    schedule_interval="@daily",
    catchup=False,
    max_active_runs=1,
    tags=["monitoring", "drift", "retrain"],
) as dag:

    # 1️⃣ Resolve latest prediction path at runtime
    resolve_prediction = PythonOperator(
        task_id="resolve_prediction",
        python_callable=resolve_latest_prediction,
        provide_context=True,
    )

    # 2️⃣ Run Evidently monitoring
    run_monitoring = BashOperator(
        task_id="run_monitor_predictions",
        bash_command="""
        PRED_PATH="{{ ti.xcom_pull(task_ids='resolve_prediction', key='prediction_path') }}"
        echo "📌 TRAIN_DATA_PATH={{ params.train_path }}"
        echo "📌 LATEST_PREDICTION_PATH=$PRED_PATH"

        python /opt/airflow/src/monitor_predictions.py \
            --train_data_path "{{ params.train_path }}" \
            --prediction_path "$PRED_PATH" \
            --status_out "{{ params.drift_status }}"
        """,
        params={
            "train_path": TRAIN_DATA_PATH,
            "drift_status": DRIFT_STATUS_FILE,
        },
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
            "MLFLOW_TRACKING_URI": os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
            "MLFLOW_ARTIFACT_URI": os.getenv(
                "MLFLOW_ARTIFACT_URI", f"gs://{GCS_BUCKET}/mlflow"
            ),
            "GCS_BUCKET": GCS_BUCKET,
            "TRAIN_DATA_PATH": TRAIN_DATA_PATH,
        },
        on_failure_callback=lambda context: notify_slack(
            "❌ Monitoring DAG failed. Check Airflow logs."
        ),
    )

    # 3️⃣ Branch: drift check
    decide_drift = BranchPythonOperator(
        task_id="decide_drift",
        python_callable=check_drift,
    )

    # 4️⃣ If drift → retrain
    trigger_retrain = TriggerDagRunOperator(
        task_id="trigger_retrain",
        trigger_dag_id="train_pipeline_dag",
        wait_for_completion=False,
    )

    # 5️⃣ If no drift → end
    no_drift = EmptyOperator(task_id="no_drift")

    # DAG flow
    resolve_prediction >> run_monitoring >> decide_drift
    decide_drift >> [trigger_retrain, no_drift]
