from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
import mlflow
from mlflow.tracking import MlflowClient
import requests
import json
import os

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
}

# -----------------------
# Config (Airflow Variables / .env)
# -----------------------
MODEL_NAME = Variable.get("MODEL_NAME", default_var=os.getenv("MODEL_NAME", "loan_default_model"))
FROM_ALIAS = Variable.get("PROMOTE_FROM_ALIAS", default_var="staging")
TO_ALIAS = Variable.get("PROMOTE_TO_ALIAS", default_var="production")

MLFLOW_TRACKING_URI = Variable.get(
    "MLFLOW_TRACKING_URI",
    default_var=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
)

SLACK_WEBHOOK_URL = Variable.get("SLACK_WEBHOOK_URL", default_var=os.getenv("SLACK_WEBHOOK_URL", ""))
ALERT_EMAILS = Variable.get("ALERT_EMAILS", default_var=os.getenv("ALERT_EMAILS", ""))

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
client = MlflowClient()


# -----------------------
# Core: promotion
# -----------------------
def promote_model(**context):
    conf = context.get("dag_run").conf or {}
    model_name = conf.get("model_name", MODEL_NAME)
    from_alias = conf.get("from_alias", FROM_ALIAS).lower()
    to_alias = conf.get("to_alias", TO_ALIAS).lower()
    version_to_promote = conf.get("model_version", None)

    print(f"🚀 Starting promotion for model: {model_name}")
    print(f"   From alias='{from_alias}' → To alias='{to_alias}'")
    print(f"   Tracking URI={MLFLOW_TRACKING_URI}")

    if not version_to_promote:
        try:
            alias_info = client.get_model_version_by_alias(model_name, from_alias)
            version_to_promote = alias_info.version
            print(f"ℹ️ Resolved latest '{from_alias}' version: {version_to_promote}")
        except Exception as e:
            msg = f"❌ Could not resolve alias '{from_alias}' for model '{model_name}': {e}"
            context["ti"].xcom_push(key="exception", value=msg)
            raise RuntimeError(msg)

    try:
        # Promote alias
        client.set_registered_model_alias(
            name=model_name,
            alias=to_alias,
            version=version_to_promote,
        )

        # Audit tags
        trigger_source = conf.get("trigger_source", "Airflow DAG")
        triggered_by = conf.get("triggered_by", "automated_rule")
        client.set_model_version_tag(model_name, version_to_promote, "promoted_from", from_alias)
        client.set_model_version_tag(model_name, version_to_promote, "promoted_to", to_alias)
        client.set_model_version_tag(model_name, version_to_promote, "trigger_source", trigger_source)
        client.set_model_version_tag(model_name, version_to_promote, "triggered_by", triggered_by)

        # Push XComs for downstream tasks
        ti = context["ti"]
        ti.xcom_push(key="promoted_model_name", value=model_name)
        ti.xcom_push(key="promoted_model_version", value=str(version_to_promote))
        ti.xcom_push(key="promoted_from_alias", value=from_alias)
        ti.xcom_push(key="promoted_to_alias", value=to_alias)

        print(f"✅ Promotion successful: '{model_name}' v{version_to_promote} from '{from_alias}' → '{to_alias}'.")

    except Exception as e:
        msg = f"❌ Promotion failed for {model_name}: {e}"
        context["ti"].xcom_push(key="exception", value=msg)
        raise RuntimeError(msg)


# -----------------------
# Slack helpers
# -----------------------
def _post_to_slack(text: str):
    if not SLACK_WEBHOOK_URL:
        print("ℹ️ SLACK_WEBHOOK_URL not set; skipping Slack notification.")
        return
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"text": text}),
            timeout=10,
        )
        print(f"Slack response: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"⚠️ Slack notification failed: {e}")


def notify_slack_success(**context):
    try:
        ti = context["ti"]
        model = ti.xcom_pull(key="promoted_model_name")
        version = ti.xcom_pull(key="promoted_model_version")
        from_alias = ti.xcom_pull(key="promoted_from_alias")
        to_alias = ti.xcom_pull(key="promoted_to_alias")
        _post_to_slack(f"✅ *Model promoted*: `{model}` v{version} from `{from_alias}` → `{to_alias}`")
    except Exception as e:
        print(f"⚠️ Slack success notification failed: {e}")


def notify_slack_failure(context):
    try:
        dag_id = context.get("dag").dag_id if context.get("dag") else ""
        task_id = context.get("task_instance").task_id if context.get("task_instance") else ""
        err = context.get("exception", "")
        _post_to_slack(f"❌ *Promotion failed* in DAG `{dag_id}`, task `{task_id}`:\n```{err}```")
    except Exception as e:
        print(f"⚠️ Slack failure notification failed: {e}")


# -----------------------
# DAG
# -----------------------
with DAG(
    dag_id="promote_model_dag",
    default_args=default_args,
    description="Promotes MLflow model from staging to production with alerts",
    schedule_interval=None,  # only triggered, never scheduled
    start_date=datetime(2025, 8, 1),
    catchup=False,
    tags=["mlflow", "model", "promotion"],
) as dag:

    do_promotion = PythonOperator(
        task_id="promote_model_task",
        python_callable=promote_model,
        on_failure_callback=notify_slack_failure,
    )

    slack_success = PythonOperator(
        task_id="slack_notify_success",
        python_callable=notify_slack_success,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    email_success = EmailOperator(
        task_id="email_notify_success",
        to=[e.strip() for e in ALERT_EMAILS.split(",") if e.strip()],
        subject="✅ MLflow Promotion Succeeded",
        html_content="""
            <p><b>Model promotion succeeded.</b></p>
            <p>Model: {{ ti.xcom_pull(key='promoted_model_name') }}<br/>
               Version: {{ ti.xcom_pull(key='promoted_model_version') }}<br/>
               From: {{ ti.xcom_pull(key='promoted_from_alias') }} → To: {{ ti.xcom_pull(key='promoted_to_alias') }}
            </p>
        """,
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    email_failure = EmailOperator(
        task_id="email_notify_failure",
        to=[e.strip() for e in ALERT_EMAILS.split(",") if e.strip()],
        subject="❌ MLflow Promotion Failed",
        html_content="""
            <p><b>Model promotion failed.</b></p>
            <p>Error: {{ ti.xcom_pull(task_ids='promote_model_task', key='exception') }}</p>
            <p>Check Airflow logs for more details.</p>
        """,
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    do_promotion >> [slack_success, email_success]
    do_promotion >> email_failure
