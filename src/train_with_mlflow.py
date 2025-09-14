import argparse
import json
import os
import shutil
import socket

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from mlflow.models.signature import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


# -----------------------
# Constants
# -----------------------
BASE_DIR = "/opt/airflow"  # Mounted project root in container
ARTIFACT_DIR = os.path.join(BASE_DIR, "artifacts")
TMP_ARTIFACT_DIR = "/tmp/artifacts"  # Always writable in container

os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(TMP_ARTIFACT_DIR, exist_ok=True)


# -----------------------
# MLflow Configuration
# -----------------------
def is_host_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


GCS_BUCKET = os.getenv("GCS_BUCKET", "loan-default-artifacts-loan-default-mlops")
mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
mlflow_artifact_uri = os.getenv("MLFLOW_ARTIFACT_URI", f"gs://{GCS_BUCKET}/mlflow")
vertex_training = os.getenv("VERTEX_AI_TRAINING", "0") == "1"

if vertex_training:
    # ✅ Vertex AI: use MLflow server for registry + metrics, GCS for artifacts
    print(f"✅ Vertex AI mode. Registry+Metrics → {mlflow_tracking_uri}, Artifacts → {mlflow_artifact_uri}")
    mlflow.set_tracking_uri(mlflow_tracking_uri)
else:
    # ✅ Local Airflow / Docker
    if mlflow_tracking_uri and "http://mlflow:5000" in mlflow_tracking_uri:
        if is_host_reachable("mlflow", 5000):
            print(f"✅ Using MLflow server: {mlflow_tracking_uri}")
            mlflow.set_tracking_uri(mlflow_tracking_uri)
        else:
            print("⚠️ MLflow server not reachable, falling back to file:// logging")
            mlflow.set_tracking_uri(f"file://{os.path.join(BASE_DIR, 'mlruns')}")
    else:
        mlflow.set_tracking_uri(f"file://{os.path.join(BASE_DIR, 'mlruns')}")

EXPERIMENT_NAME = "loan_default_experiment"
client = MlflowClient()

experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
if experiment is None:
    experiment_id = client.create_experiment(
        EXPERIMENT_NAME,
        artifact_location=mlflow_artifact_uri,  # ✅ always GCS artifacts
    )
else:
    experiment_id = experiment.experiment_id


# -----------------------
# Data Loading
# -----------------------
def load_data(path: str):
    if path.startswith("gs://"):
        print(f"☁️ Loading training data from GCS: {path}")
    else:
        print(f"📥 Loading training data from local path: {path}")
    df = pd.read_csv(path)
    X = df.drop("loan_status", axis=1)
    y = df["loan_status"]
    return (
        train_test_split(X, y, test_size=0.2, stratify=y, random_state=42),
        df.columns[:-1],
    )


# -----------------------
# Model Training
# -----------------------
def train_xgboost(X_train, y_train, custom_params=None):
    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()
    base_params = {
        "eval_metric": "logloss",
        "scale_pos_weight": scale_pos_weight,
        "random_state": 42,
        "use_label_encoder": False,
    }
    if custom_params:
        base_params.update(custom_params)

    model = XGBClassifier(**base_params)
    model.fit(X_train, y_train)
    return model, base_params


# -----------------------
# Evaluation
# -----------------------
def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "AUC": roc_auc_score(y_test, y_proba),
        "F1": f1_score(y_test, y_pred),
        "Precision": precision_score(y_test, y_pred),
        "Recall": recall_score(y_test, y_pred),
    }


# -----------------------
# Plot Helpers
# -----------------------
def save_plot_safely(fig, filename):
    tmp_path = os.path.join(TMP_ARTIFACT_DIR, os.path.basename(filename))
    fig.savefig(tmp_path)
    plt.close(fig)
    try:
        shutil.copy2(tmp_path, filename)
        return filename
    except PermissionError:
        print(f"⚠️ Permission denied writing {filename}. Using temp file instead.")
        return tmp_path


def save_feature_importance_plot(model, feature_names, filename):
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1][:10]
    top_features = [feature_names[i] for i in sorted_idx]
    top_importances = importances[sorted_idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_features[::-1], top_importances[::-1])
    ax.set_xlabel("Importance")
    ax.set_title("Top 10 Feature Importances")
    plt.tight_layout()
    return save_plot_safely(fig, filename)


def save_roc_curve_plot(y_test, y_proba, filename):
    fpr, tpr, _ = roc_curve(y_test, y_proba)
    auc_score = roc_auc_score(y_test, y_proba)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(fpr, tpr, label=f"AUC = {auc_score:.2f}")
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    return save_plot_safely(fig, filename)


def save_confusion_matrix_plot(y_test, y_pred, filename):
    cm = confusion_matrix(y_test, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    fig, ax = plt.subplots()
    disp.plot(cmap=plt.cm.Blues, ax=ax)
    ax.set_title("Confusion Matrix")
    plt.tight_layout()
    return save_plot_safely(fig, filename)


# -----------------------
# MLflow Logging
# -----------------------
def log_and_register_model(
    model,
    X_test,
    y_test,
    metrics,
    params,
    model_name,
    alias=None,
    feature_names=None,
    experiment_id=None,
):
    with mlflow.start_run(experiment_id=experiment_id) as run:
        run_id = run.info.run_id
        print(f"Run ID: {run_id}")

        mlflow.log_metrics(metrics)
        mlflow.log_params(params)

        input_example = X_test.iloc[:1]
        signature = infer_signature(X_test, model.predict(X_test))
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            registered_model_name=model_name,
            signature=signature,
            input_example=input_example,
            pip_requirements=[
                "mlflow==3.1.4",
                "xgboost==1.7.6",
                "scikit-learn",
                "pandas",
                "numpy",
            ],
        )

        plot_paths = []
        if feature_names is not None:
            plot_paths.append(
                save_feature_importance_plot(
                    model, feature_names, os.path.join(ARTIFACT_DIR, "feature_importance.png")
                )
            )
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        plot_paths.append(
            save_roc_curve_plot(y_test, y_proba, os.path.join(ARTIFACT_DIR, "roc_curve.png"))
        )
        plot_paths.append(
            save_confusion_matrix_plot(y_test, y_pred, os.path.join(ARTIFACT_DIR, "confusion_matrix.png"))
        )

        for path in plot_paths:
            mlflow.log_artifact(path, artifact_path="artifacts")

        try:
            mlflow.log_artifacts(ARTIFACT_DIR, artifact_path="artifacts")
        except PermissionError:
            print(f"⚠️ Skipped logging from {ARTIFACT_DIR} due to permissions.")

        if alias:
            latest_version = client.get_latest_versions(model_name, stages=[])[0].version
            client.set_registered_model_alias(
                name=model_name, alias=alias.lower(), version=latest_version
            )
            print(f"Assigned alias '{alias}' to version {latest_version}")


# -----------------------
# CLI Entry Point
# -----------------------
def main(args):
    print(f"🚀 Training XGBoost for model: {args.model_name}")
    (X_train, X_test, y_train, y_test), feature_names = load_data(args.data_path)

    tuned_params = None
    if args.params_path:
        if args.params_path.startswith("gs://"):
            try:
                print(f"☁️ Fetching tuned params from GCS: {args.params_path}")
                tuned_params = pd.read_json(args.params_path, lines=True).iloc[0].to_dict()
            except Exception as e:
                print(f"⚠️ Could not load tuned params from GCS: {e}")
        elif os.path.exists(args.params_path):
            print(f"📥 Loading tuned params locally: {args.params_path}")
            with open(args.params_path, "r") as f:
                tuned_params = json.load(f)

    model, params_used = train_xgboost(X_train, y_train, tuned_params)
    metrics = evaluate_model(model, X_test, y_test)
    params_used["model_type"] = "xgboost"

    log_and_register_model(
        model,
        X_test,
        y_test,
        metrics,
        params_used,
        model_name=args.model_name,
        alias=args.alias,
        feature_names=feature_names,
        experiment_id=experiment_id,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_path",
        default=os.getenv(
            "TRAIN_DATA_PATH",
            os.path.join(BASE_DIR, "data", "loan_default_selected_features_clean.csv"),
        ),
        help="Path to training data (CSV). Supports gs:// paths if gcsfs is installed.",
    )
    parser.add_argument("--model_name", default="loan_default_model")
    parser.add_argument("--alias", default="staging")
    parser.add_argument("--params_path", default=None)
    args = parser.parse_args()

    main(args)
