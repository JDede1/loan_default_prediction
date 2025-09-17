from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.models import Variable
import os
from google.cloud import storage  # ✅ use Python client

# -----------------------
# Defaults
# -----------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
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

# ✅ Persistent Optuna DB inside artifacts folder
OPTUNA_DB_PATH = "/opt/airflow/artifacts/optuna_study.db"

# -----------------------
# Helper functions
# -----------------------
def upload_to_gcs(local_path, bucket_name, blob_name):
    """Upload file to GCS using Python client."""
    client = storage.Client.from_service_account_json(
        "/opt/airflow/keys/gcs-service-account.json"
    )
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    print(f"✅ Uploaded {local_path} → gs://{bucket_name}/{blob_name}")

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

    # 1️⃣ Run Optuna tuning (with persistent SQLite backend)
    run_tuning = BashOperator(
        task_id="run_optuna_tuning",
        bash_command=(
            "python /opt/airflow/src/tune_xgboost_with_optuna.py "
            f"--data_path {TRAIN_DATA_PATH} "
            "--trials 10 "
            f"--output_params {BEST_PARAMS_PATH}"
        ),
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS",
                "/opt/airflow/keys/gcs-service-account.json",
            ),
            "OPTUNA_DB_PATH": OPTUNA_DB_PATH,
        },
    )

    # 2️⃣ Upload best params JSON to GCS
    upload_best_params = PythonOperator(
        task_id="upload_best_params",
        python_callable=upload_to_gcs,
        op_args=[BEST_PARAMS_PATH, GCS_BUCKET, "artifacts/best_xgb_params.json"],
    )

    # 3️⃣ Upload Optuna DB to GCS (for resuming studies anywhere)
    upload_optuna_db = PythonOperator(
        task_id="upload_optuna_db",
        python_callable=upload_to_gcs,
        op_args=[OPTUNA_DB_PATH, GCS_BUCKET, "artifacts/optuna_study.db"],
    )

    # Flow
    run_tuning >> [upload_best_params, upload_optuna_db]
