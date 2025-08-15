import os
import pandas as pd
import optuna
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

# ---------- Constants ----------
BASE_DIR = "/opt/airflow"  # Mounted project root inside container
DATA_PATH = os.path.join(BASE_DIR, "data", "loan_default_selected_features_clean.csv")

# ---------- Load Data ----------
def load_data(path):
    df = pd.read_csv(path)
    X = df.drop("loan_status", axis=1)
    y = df["loan_status"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

# ---------- Objective Function ----------
def objective(trial):
    X_train, X_test, y_train, y_test = load_data(DATA_PATH)

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

    return auc  # Maximize AUC

# ---------- Run Study ----------
if __name__ == "__main__":
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=25)

    print("\n📊 Best trial:")
    print(study.best_trial)

    print("\n🏆 Best hyperparameters:")
    for key, value in study.best_params.items():
        print(f"{key}: {value}")
