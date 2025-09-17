import argparse
import json
import os

import optuna
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


# -----------------------
# Load Data
# -----------------------
def load_data(path: str):
    """Load CSV from local or GCS (gs://...) path."""
    print(f"📥 Loading data from: {path}")
    df = pd.read_csv(path)  # gcsfs enables pd.read_csv(gs://...) automatically
    X = df.drop("loan_status", axis=1)
    y = df["loan_status"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)


# -----------------------
# Objective Function
# -----------------------
def make_objective(data_path: str):
    def objective(trial):
        X_train, X_test, y_train, y_test = load_data(data_path)

        scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

        params = {
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "gamma": trial.suggest_float("gamma", 0, 5),
            "reg_alpha": trial.suggest_float("reg_alpha", 0, 5),
            "reg_lambda": trial.suggest_float("reg_lambda", 0, 5),
            "scale_pos_weight": scale_pos_weight,
            "eval_metric": "logloss",
            "use_label_encoder": False,
            "random_state": 42,
        }

        model = XGBClassifier(**params)
        model.fit(X_train, y_train)
        y_proba = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_proba)

        return auc  # maximize AUC

    return objective


# -----------------------
# Main
# -----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_path",
        default=os.getenv(
            "TRAIN_DATA_PATH",
            "/opt/airflow/data/loan_default_selected_features_clean.csv",
        ),
        help="Path to training data (CSV). Supports gs:// paths if gcsfs is installed.",
    )
    parser.add_argument(
        "--trials", type=int, default=25, help="Number of Optuna trials"
    )
    parser.add_argument(
        "--output_params",
        default=os.getenv(
            "BEST_PARAMS_PATH", "/opt/airflow/artifacts/best_xgb_params.json"
        ),
        help="Where to save best parameters JSON (can be gs:// path).",
    )
    args = parser.parse_args()

    # ✅ Persistent Optuna storage in artifacts volume
    db_path = os.getenv("OPTUNA_DB_PATH", "/opt/airflow/artifacts/optuna_study.db")
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)  # ensure directory exists
    print(f"✅ Ensured Optuna DB directory exists: {db_dir}")

    storage_path = f"sqlite:///{db_path}"
    study = optuna.create_study(
        direction="maximize",
        study_name="loan_default_optuna",
        storage=storage_path,
        load_if_exists=True,  # resume if already exists
    )

    # Run trials
    study.optimize(make_objective(args.data_path), n_trials=args.trials)

    print("\n📊 Best trial:")
    print(study.best_trial)

    print("\n🏆 Best hyperparameters:")
    for key, value in study.best_params.items():
        print(f"{key}: {value}")

    # Save best params to JSON (local or GCS via pandas + gcsfs)
    if args.output_params.startswith("gs://"):
        tmp_path = "/tmp/best_xgb_params.json"
        with open(tmp_path, "w") as f:
            json.dump(study.best_params, f, indent=2)
        df = pd.DataFrame([study.best_params])
        df.to_json(args.output_params, orient="records", lines=True)
        print(f"\n✅ Best parameters saved to GCS: {args.output_params}")
    else:
        os.makedirs(os.path.dirname(args.output_params), exist_ok=True)
        with open(args.output_params, "w") as f:
            json.dump(study.best_params, f, indent=2)
        print(f"\n✅ Best parameters saved locally to: {args.output_params}")
