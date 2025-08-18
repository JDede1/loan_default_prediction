from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
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
# Config (from Airflow Variables / .env)
# -----------------------
MODEL_NAME = Variable.get(
    "MODEL_NAME",
    default_var=os.getenv("MODEL_NAME", "loan_default_model"),
)
MODEL_ALIAS = Variable.get(
    "MODEL_ALIAS",
    default_var=os.getenv("MODEL_ALIAS", "staging"),
)

# ✅ Standardized to Terraform bucket
PREDICTION_INPUT_PATH = Variable.get(
    "PREDICTION_INPUT_PATH",
    default_var=os.getenv(
        "PREDICTION_INPUT_PATH",
        "gs://loan-default-artifacts-loan-default-mlops/data/batch_input.csv",
    ),
)

# ✅ Base output path — batch_predict.py will append timestamp
PREDICTION_OUTPUT_PATH = Variable.get(
    "PREDICTION_OUTPUT_PATH",
    default_var=os.getenv(
        "PREDICTION_OUTPUT_PATH",
        "gs://loan-default-artifacts-loan-default-mlops/predictions/predictions.csv",
    ),
)

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

    # 1️⃣ Run batch predictions
    run_batch_prediction = BashOperator(
        task_id="run_batch_prediction",
        bash_command=(
            "python /opt/airflow/src/batch_predict.py "
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
            "MLFLOW_TRACKING_URI": os.getenv(
                "MLFLOW_TRACKING_URI", "http://mlflow:5000"
            ),
            "MLFLOW_ARTIFACT_URI": os.getenv(
                "MLFLOW_ARTIFACT_URI",
                f"gs://{os.getenv('GCS_BUCKET', 'loan-default-artifacts-loan-default-mlops')}/mlflow",
            ),
            "GCS_BUCKET": os.getenv(
                "GCS_BUCKET", "loan-default-artifacts-loan-default-mlops"
            ),
            "PREDICTION_INPUT_PATH": PREDICTION_INPUT_PATH,
            "PREDICTION_OUTPUT_PATH": PREDICTION_OUTPUT_PATH,
            # ✅ Ensure predictions are uploaded to GCS
            "STORAGE_BACKEND": "gcs",
        },
    )

    # 2️⃣ Save latest prediction marker (robust version with error handling)
    save_latest_marker = BashOperator(
        task_id="save_latest_marker",
        bash_command="""
        gcloud auth activate-service-account --key-file=/opt/airflow/keys/gcs-service-account.json
        LATEST_FILE=$(gsutil ls gs://loan-default-artifacts-loan-default-mlops/predictions/ | grep predictions_ | sort | tail -n 1 || echo "")
        if [ -z "$LATEST_FILE" ]; then
            echo "❌ ERROR: No prediction files found in bucket" && exit 1
        else
            echo "📌 Latest prediction file: $LATEST_FILE"
            echo $LATEST_FILE > /tmp/latest_prediction.txt
            gsutil cp /tmp/latest_prediction.txt gs://loan-default-artifacts-loan-default-mlops/predictions/latest_prediction.txt
        fi
        """,
        cwd="/opt/airflow",
        env={
            "GOOGLE_APPLICATION_CREDENTIALS": "/opt/airflow/keys/gcs-service-account.json",
        },
    )

    # 3️⃣ Trigger monitoring DAG after predictions
    trigger_monitoring = TriggerDagRunOperator(
        task_id="trigger_monitoring",
        trigger_dag_id="monitoring_dag",
        wait_for_completion=False,
    )

    # DAG flow
    run_batch_prediction >> save_latest_marker >> trigger_monitoring
