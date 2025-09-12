from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable
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
# Config (Airflow Variables / .env)
# -----------------------
TRAIN_DATA_PATH = Variable.get(
    "TRAIN_DATA_PATH",
    default_var=os.getenv(
        "TRAIN_DATA_PATH",
        "gs://loan-default-artifacts-loan-default-mlops/data/loan_default_selected_features_clean.csv",
    ),
)

BEST_PARAMS_PATH = Variable.get(
    "BEST_PARAMS_PATH",
    default_var=os.getenv(
        "BEST_PARAMS_PATH", "/opt/airflow/artifacts/best_xgb_params.json"
    ),
)

GCS_BUCKET = Variable.get(
    "GCS_BUCKET",
    default_var=os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"),
)

# -----------------------
# DAG Definition
# -----------------------
with DAG(
    dag_id="tune_hyperparams_dag",
    default_args=default_args,
    description="Run Optuna to tune XGBoost hyperparameters",
    schedule_interval=None,  # run only when triggered
    start_date=datetime(2025, 8, 1),
    catchup=False,
    tags=["optuna", "tuning", "xgboost"],
) as dag:

    # 1️⃣ Run Optuna tuning
    run_tuning = BashOperator(
        task_id="run_optuna_tuning",
        bash_command=(
            "python /opt/airflow/src/tune_xgboost_with_optuna.py "
            f"--data_path {TRAIN_DATA_PATH} "
            "--trials 25 "
            f"--output_params {BEST_PARAMS_PATH}"
        ),
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
        },
    )

    # 2️⃣ Upload best params to GCS (for portability)
    upload_best_params = BashOperator(
        task_id="upload_best_params",
        bash_command=(
            "gcloud auth activate-service-account --key-file=/opt/airflow/keys/gcs-service-account.json && "
            f"gsutil cp {BEST_PARAMS_PATH} gs://{GCS_BUCKET}/artifacts/best_xgb_params.json"
        ),
    )

    run_tuning >> upload_best_params
