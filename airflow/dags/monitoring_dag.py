from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import os

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# -----------------------
# Load Config from Airflow Variables / .env
# -----------------------
LATEST_PREDICTION_PATH = Variable.get(
    "LATEST_PREDICTION_PATH",
    default_var=os.getenv("LATEST_PREDICTION_PATH", "")
)

# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="evidently_monitoring_daily",
    default_args=default_args,
    description="Daily monitoring with Evidently (runs inside Airflow container)",
    start_date=datetime(2025, 8, 1),
    schedule_interval="@daily",  # Daily monitoring
    catchup=False,
    max_active_runs=1,  # Prevent overlapping runs
    tags=["monitoring", "evidently"],
) as dag:

    # If LATEST_PREDICTION_PATH is provided, pass it as an arg to the script
    if LATEST_PREDICTION_PATH:
        bash_cmd = f"python /opt/airflow/src/monitor_predictions.py --prediction_path {LATEST_PREDICTION_PATH}"
    else:
        bash_cmd = "python /opt/airflow/src/monitor_predictions.py"

    run_monitoring = BashOperator(
        task_id="run_monitor_predictions",
        bash_command=bash_cmd,
        cwd="/opt/airflow",
    )

    run_monitoring
