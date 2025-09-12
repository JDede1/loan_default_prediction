import os
import json

# Load .env manually if needed
from dotenv import load_dotenv
load_dotenv(".env")

# Define the variables we care about
keys = [
    "PROJECT_ID",
    "REGION",
    "TRAINER_IMAGE_URI",
    "MODEL_NAME",
    "MODEL_ALIAS",
    "PROMOTE_FROM_ALIAS",
    "PROMOTE_TO_ALIAS",
    "PROMOTION_AUC_THRESHOLD",
    "PROMOTION_F1_THRESHOLD",
    "TRAIN_DATA_PATH",
    "BEST_PARAMS_PATH",
    "GCS_BUCKET",
    "MLFLOW_TRACKING_URI",
    "MLFLOW_ARTIFACT_URI",
    "SLACK_WEBHOOK_URL",
    "ALERT_EMAILS"
]

variables = {k: os.getenv(k, "") for k in keys}

# Save as airflow/variables.json
with open("airflow/variables.json", "w") as f:
    json.dump(variables, f, indent=2)

print("✅ Exported variables to airflow/variables.json")
