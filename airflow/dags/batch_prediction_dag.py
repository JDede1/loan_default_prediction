from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.models import Variable
from datetime import datetime, timedelta
import os

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
# Load Config from Airflow Variables (fallback to .env)
# -----------------------
MODEL_NAME = Variable.get("MODEL_NAME", default_var=os.getenv("MODEL_NAME", "loan_default_model"))
MODEL_ALIAS = Variable.get("MODEL_ALIAS", default_var=os.getenv("MODEL_ALIAS", "staging"))
PREDICTION_INPUT_PATH = Variable.get("PREDICTION_INPUT_PATH", default_var=os.getenv("PREDICTION_INPUT_PATH", "/opt/airflow/data/batch_input.csv"))
PREDICTION_OUTPUT_PATH = Variable.get("PREDICTION_OUTPUT_PATH", default_var=os.getenv("PREDICTION_OUTPUT_PATH", "/opt/airflow/artifacts/predictions.csv"))

# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="batch_prediction_dag",
    default_args=default_args,
    description="Batch loan default prediction using registered MLflow model",
    schedule_interval="@daily",  # Daily batch prediction
    start_date=datetime(2025, 8, 1),
    catchup=False,
    max_active_runs=1,  # Prevent overlapping runs
    tags=["batch", "prediction", "mlflow"],
) as dag:

    run_batch_prediction = BashOperator(
        task_id="run_batch_prediction",
        bash_command=f"""
            python /opt/airflow/src/batch_predict.py \
              --model_name {MODEL_NAME} \
              --alias {MODEL_ALIAS} \
              --input_path {PREDICTION_INPUT_PATH} \
              --output_path {PREDICTION_OUTPUT_PATH}
        """,
        cwd="/opt/airflow"
    )

    trigger_monitoring = TriggerDagRunOperator(
        task_id="trigger_monitoring",
        trigger_dag_id="evidently_monitoring_daily",
        wait_for_completion=False
    )

    run_batch_prediction >> trigger_monitoring
