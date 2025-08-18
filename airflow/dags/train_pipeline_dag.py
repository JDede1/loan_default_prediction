from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
import mlflow
from mlflow.tracking import MlflowClient
import os
import requests
from airflow.utils.email import send_email

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
# Config
# -----------------------
MODEL_NAME = Variable.get(
    "MODEL_NAME", default_var=os.getenv("MODEL_NAME", "loan_default_model")
)
FROM_ALIAS = Variable.get("PROMOTE_FROM_ALIAS", default_var="staging")
TO_ALIAS = Variable.get("PROMOTE_TO_ALIAS", default_var="production")
AUC_THRESHOLD = float(Variable.get("PROMOTION_AUC_THRESHOLD", default_var="0.75"))
F1_THRESHOLD = float(
    Variable.get("PROMOTION_F1_THRESHOLD", default_var="0")
)  # 0 = ignore

SLACK_WEBHOOK_URL = Variable.get(
    "SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", "")
)
ALERT_EMAILS = Variable.get("ALERT_EMAILS", default_var=os.getenv("ALERT_EMAILS", ""))

# Extra context for promotion audit tags
TRIGGER_SOURCE = Variable.get(
    "PROMOTION_TRIGGER_SOURCE", default_var="train_pipeline_dag"
)
TRIGGERED_BY = Variable.get(
    "PROMOTION_TRIGGERED_BY", default_var="automated_weekly_job"
)

# ✅ Force MLflow to use server
MLFLOW_TRACKING_URI = Variable.get(
    "MLFLOW_TRACKING_URI",
    default_var=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
)

# ✅ Unified training data path
TRAIN_DATA_PATH = Variable.get(
    "TRAIN_DATA_PATH",
    default_var=os.getenv(
        "TRAIN_DATA_PATH", "/opt/airflow/data/loan_default_selected_features_clean.csv"
    ),
)

# ✅ Best params path aligned with tuning script
BEST_PARAMS_PATH = Variable.get(
    "BEST_PARAMS_PATH",
    default_var=os.getenv(
        "BEST_PARAMS_PATH", "/opt/airflow/artifacts/best_xgb_params.json"
    ),
)

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
client = MlflowClient()


# -----------------------
# Notifications
# -----------------------
def notify_slack(message: str):
    if SLACK_WEBHOOK_URL:
        try:
            requests.post(SLACK_WEBHOOK_URL, json={"text": message})
        except Exception as e:
            print(f"⚠️ Slack notification failed: {e}")


def notify_email(subject: str, html_content: str):
    if ALERT_EMAILS:
        try:
            send_email(
                to=ALERT_EMAILS.split(","), subject=subject, html_content=html_content
            )
        except Exception as e:
            print(f"⚠️ Email notification failed: {e}")


# -----------------------
# Branch: decide whether to promote
# -----------------------
def decide_promotion(ti):
    try:
        alias_info = client.get_model_version_by_alias(MODEL_NAME, FROM_ALIAS.lower())
        version = alias_info.version
        run_id = alias_info.run_id
    except Exception as e:
        msg = f"❌ Could not find alias '{FROM_ALIAS}' for model '{MODEL_NAME}': {e}"
        notify_slack(msg)
        notify_email("❌ Model Promotion Failed", msg)
        return "skip_promotion"

    run_data = client.get_run(run_id).data
    auc = run_data.metrics.get("AUC")
    f1 = run_data.metrics.get("F1")

    if auc is None:
        msg = f"⚠️ AUC metric missing for run {run_id}"
        notify_slack(msg)
        notify_email("⚠️ Model Promotion Skipped", msg)
        return "skip_promotion"

    ti.xcom_push(key="model_version", value=str(version))

    print(
        f"📊 {FROM_ALIAS} model: version={version}, AUC={auc}, F1={f1}, thresholds: AUC>={AUC_THRESHOLD}, F1>={F1_THRESHOLD}"
    )

    if auc >= AUC_THRESHOLD and (
        F1_THRESHOLD == 0 or (f1 is not None and f1 >= F1_THRESHOLD)
    ):
        msg = f"✅ Model {MODEL_NAME} v{version} meets promotion criteria (AUC={auc}, F1={f1})"
        notify_slack(msg)
        notify_email("✅ Model Promotion Approved", msg)
        return "trigger_promotion"
    else:
        msg = f"❌ Model {MODEL_NAME} v{version} did NOT meet promotion criteria (AUC={auc}, F1={f1})"
        notify_slack(msg)
        notify_email("❌ Model Promotion Skipped", msg)
        return "skip_promotion"


# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="train_model_with_mlflow",
    default_args=default_args,
    start_date=datetime(2025, 8, 1),
    schedule_interval="@weekly",  # Weekly retraining
    catchup=False,
    max_active_runs=1,
    tags=["mlflow", "training", "promotion"],
) as dag:

    # 1️⃣ Train model
    train_model = BashOperator(
        task_id="train_model",
        bash_command=(
            "python /opt/airflow/src/train_with_mlflow.py "
            f'--data_path "{TRAIN_DATA_PATH}" '
            f"--params_path {BEST_PARAMS_PATH} "
            f"--model_name {MODEL_NAME} "
            f"--alias {FROM_ALIAS}"
        ),
        cwd="/opt/airflow",
        env={
            # ✅ Ensure training script sees critical env vars
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
            "MLFLOW_TRACKING_URI": MLFLOW_TRACKING_URI,
            "MLFLOW_ARTIFACT_URI": os.getenv(
                "MLFLOW_ARTIFACT_URI", f"gs://{os.getenv('GCS_BUCKET', '')}/mlflow"
            ),
            "GCS_BUCKET": os.getenv("GCS_BUCKET", ""),
            "TRAIN_DATA_PATH": TRAIN_DATA_PATH,
        },
    )

    # 2️⃣ Decide promotion
    decide = BranchPythonOperator(
        task_id="decide_promotion",
        python_callable=decide_promotion,
    )

    # 3a️⃣ Trigger promotion DAG
    trigger_promotion = TriggerDagRunOperator(
        task_id="trigger_promotion",
        trigger_dag_id="promote_model_dag",
        conf={
            "model_name": MODEL_NAME,
            "from_alias": FROM_ALIAS,
            "to_alias": TO_ALIAS,
            "model_version": "{{ ti.xcom_pull(task_ids='decide_promotion', key='model_version') }}",
            "trigger_source": TRIGGER_SOURCE,
            "triggered_by": TRIGGERED_BY,
        },
        wait_for_completion=False,
    )

    # 3b️⃣ Skip promotion
    skip_promotion = EmptyOperator(task_id="skip_promotion")

    # 4️⃣ Join after promotion
    join_after_promotion = EmptyOperator(
        task_id="join_after_promotion",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    # 5️⃣ Trigger batch prediction
    trigger_batch_prediction = TriggerDagRunOperator(
        task_id="trigger_batch_prediction",
        trigger_dag_id="batch_prediction_dag",
        wait_for_completion=False,
    )

    # Flow
    train_model >> decide
    decide >> [trigger_promotion, skip_promotion]
    (
        [trigger_promotion, skip_promotion]
        >> join_after_promotion
        >> trigger_batch_prediction
    )
