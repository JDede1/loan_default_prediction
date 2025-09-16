from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
from airflow.operators.bash import BashOperator
import mlflow
from mlflow.tracking import MlflowClient
import os
import requests
from airflow.utils.email import send_email
from google.cloud import aiplatform
import subprocess

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
MODEL_NAME = Variable.get("MODEL_NAME", default_var=os.getenv("MODEL_NAME", "loan_default_model"))
FROM_ALIAS = Variable.get("PROMOTE_FROM_ALIAS", default_var="staging")
TO_ALIAS = Variable.get("PROMOTE_TO_ALIAS", default_var="production")
AUC_THRESHOLD = float(Variable.get("PROMOTION_AUC_THRESHOLD", default_var="0.75"))
F1_THRESHOLD = float(Variable.get("PROMOTION_F1_THRESHOLD", default_var="0"))

SLACK_WEBHOOK_URL = Variable.get("SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", ""))
ALERT_EMAILS = Variable.get("ALERT_EMAILS", default_var=os.getenv("ALERT_EMAILS", ""))

TRIGGER_SOURCE = Variable.get("PROMOTION_TRIGGER_SOURCE", default_var="train_pipeline_dag")
TRIGGERED_BY = Variable.get("PROMOTION_TRIGGERED_BY", default_var="automated_weekly_job")

# ✅ MLflow → use GCS as unified backend
GCS_BUCKET = Variable.get(
    "GCS_BUCKET",
    default_var=os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"),
)
MLFLOW_TRACKING_URI = Variable.get(
    "MLFLOW_TRACKING_URI",
    default_var=f"gs://{GCS_BUCKET}/mlruns",
)
MLFLOW_ARTIFACT_URI = f"gs://{GCS_BUCKET}/mlflow"

TRAIN_DATA_PATH = Variable.get("TRAIN_DATA_PATH", default_var=os.getenv("TRAIN_DATA_PATH", "/opt/airflow/data/loan_default_selected_features_clean.csv"))
BEST_PARAMS_PATH = Variable.get("BEST_PARAMS_PATH", default_var=os.getenv("BEST_PARAMS_PATH", "/opt/airflow/artifacts/best_xgb_params.json"))
OPTUNA_DB_PATH = "/opt/airflow/artifacts/optuna_study.db"

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
            send_email(to=ALERT_EMAILS.split(","), subject=subject, html_content=html_content)
        except Exception as e:
            print(f"⚠️ Email notification failed: {e}")

# -----------------------
# Vertex AI Training
# -----------------------
def submit_vertex_job(**kwargs):
    project = Variable.get("PROJECT_ID", default_var=os.getenv("PROJECT_ID", "loan-default-mlops"))
    region = Variable.get("REGION", default_var=os.getenv("REGION", "us-central1"))
    image_uri = Variable.get("TRAINER_IMAGE_URI", default_var=os.getenv("TRAINER_IMAGE_URI", ""))
    staging_bucket = f"gs://{GCS_BUCKET}"

    # Unique run prefix for this training
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_prefix = f"vertex_runs/{timestamp}"

    print(f"🚀 Submitting Vertex AI job with image: {image_uri}")
    print(f"   Project={project}, Region={region}, Staging Bucket={staging_bucket}")
    print(f"   Data Path={TRAIN_DATA_PATH}, Params Path={BEST_PARAMS_PATH}")
    print(f"   Run prefix={run_prefix}")

    aiplatform.init(project=project, location=region, staging_bucket=staging_bucket)

    job = aiplatform.CustomJob(
        display_name="loan-default-training",
        worker_pool_specs=[{
            "machine_spec": {"machine_type": "n1-standard-4"},
            "replica_count": 1,
            "container_spec": {
                "image_uri": image_uri,
                "command": ["python", "src/train_with_mlflow.py"],
                "args": [
                    "--data_path", TRAIN_DATA_PATH,
                    "--params_path", BEST_PARAMS_PATH,
                    "--model_name", MODEL_NAME,
                    "--alias", FROM_ALIAS,
                ],
                "env": [
                    {"name": "VERTEX_AI_TRAINING", "value": "1"},
                    {"name": "RUN_PREFIX", "value": run_prefix},
                    {"name": "GCS_BUCKET", "value": GCS_BUCKET},
                ],
            },
        }],
    )

    job.run(sync=True)
    print("✅ Vertex AI training job completed.")

    # Push run_prefix to XCom for ingestion
    kwargs["ti"].xcom_push(key="run_prefix", value=run_prefix)

# -----------------------
# Ingest Vertex outputs into MLflow
# -----------------------
def ingest_vertex_outputs(**kwargs):
    run_prefix = kwargs['ti'].xcom_pull(task_ids='train_model', key='run_prefix')
    if not run_prefix:
        raise ValueError("❌ No run_prefix found in XCom from train_model")

    cmd = [
        "python", "/opt/airflow/src/ingest_vertex_run.py",
        "--gcs_bucket", GCS_BUCKET,
        "--run_prefix", run_prefix,
        "--model_name", MODEL_NAME,
        "--alias", FROM_ALIAS,
    ]
    print(f"🚀 Running ingestion: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)

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
    print(f"📊 {FROM_ALIAS} model: version={version}, AUC={auc}, F1={f1}")

    if auc >= AUC_THRESHOLD and (F1_THRESHOLD == 0 or (f1 is not None and f1 >= F1_THRESHOLD)):
        notify_slack(f"✅ Model {MODEL_NAME} v{version} meets promotion criteria")
        notify_email("✅ Model Promotion Approved", f"Model {MODEL_NAME} v{version} promoted.")
        return "trigger_promotion"
    else:
        notify_slack(f"❌ Model {MODEL_NAME} v{version} did NOT meet promotion criteria")
        notify_email("❌ Model Promotion Skipped", f"Model {MODEL_NAME} v{version} skipped.")
        return "skip_promotion"

# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="train_pipeline_dag",
    default_args=default_args,
    start_date=datetime(2025, 8, 1),
    schedule_interval="@weekly",
    catchup=False,
    max_active_runs=1,
    tags=["mlflow", "training", "promotion"],
) as dag:

    download_artifacts = BashOperator(
        task_id="download_artifacts",
        bash_command=(
            f"if [ -f {BEST_PARAMS_PATH} ]; then "
            "  echo '✅ Using existing best_xgb_params.json'; "
            "else "
            "  gcloud auth activate-service-account "
            "  --key-file=/opt/airflow/keys/gcs-service-account.json && "
            f"  gsutil cp gs://{GCS_BUCKET}/artifacts/best_xgb_params.json {BEST_PARAMS_PATH} || echo '⚠️ No best_xgb_params.json found'; "
            "fi; "
            "gcloud auth activate-service-account "
            "--key-file=/opt/airflow/keys/gcs-service-account.json && "
            f"gsutil cp gs://{GCS_BUCKET}/artifacts/optuna_study.db {OPTUNA_DB_PATH} || echo '⚠️ No optuna_study.db found'"
        ),
        cwd="/opt/airflow",
    )

    train_model = PythonOperator(
        task_id="train_model",
        python_callable=submit_vertex_job,
        provide_context=True,
    )

    ingest_vertex = PythonOperator(
        task_id="ingest_vertex_run",
        python_callable=ingest_vertex_outputs,
        provide_context=True,
    )

    decide = BranchPythonOperator(task_id="decide_promotion", python_callable=decide_promotion)
    
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
    
    skip_promotion = EmptyOperator(task_id="skip_promotion")
    
    join_after_promotion = EmptyOperator(
        task_id="join_after_promotion",
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
 
    trigger_batch_prediction = TriggerDagRunOperator(
        task_id="trigger_batch_prediction",
        trigger_dag_id="batch_prediction_dag",
        wait_for_completion=False,
    )

    download_artifacts >> train_model >> ingest_vertex >> decide
    decide >> [trigger_promotion, skip_promotion]
    [trigger_promotion, skip_promotion] >> join_after_promotion >> trigger_batch_prediction
