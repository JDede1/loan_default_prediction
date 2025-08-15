import pandas as pd
import argparse
import os
import joblib

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, precision_score, recall_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# ------------------------
# 1. Load and Split Data
# ------------------------
def load_data(data_path):
    df = pd.read_csv(data_path)
    X = df.drop("loan_status", axis=1)
    y = df["loan_status"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

# ------------------------
# 2. Select Model
# ------------------------
def get_model(model_name, y_train):
    if model_name == "xgboost":
        return XGBClassifier(
            eval_metric="logloss",
            scale_pos_weight=(y_train == 0).sum() / (y_train == 1).sum(),
            random_state=42
        )

    elif model_name == "logreg":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))
        ])

    elif model_name == "random_forest":
        return RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)

    else:
        raise ValueError(f"Unsupported model: {model_name}")

# ------------------------
# 3. Evaluate Model
# ------------------------
def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    return {
        "AUC": roc_auc_score(y_test, y_proba),
        "F1": f1_score(y_test, y_pred),
        "Precision": precision_score(y_test, y_pred),
        "Recall": recall_score(y_test, y_pred)
    }

# ------------------------
# 4. Main Script
# ------------------------
def main(args):
    print(f"Starting training with model: {args.model}")
    X_train, X_test, y_train, y_test = load_data(args.data_path)

    model = get_model(args.model, y_train)
    model.fit(X_train, y_train)

    metrics = evaluate_model(model, X_test, y_test)
    print(f"Metrics: {metrics}")

    # Create output directory
    os.makedirs(args.output_path, exist_ok=True)

    # Save trained model
    model_file = os.path.join(args.output_path, f"{args.model}_model.pkl")
    joblib.dump(model, model_file)
    print(f"Model saved to: {model_file}")

    # Save metrics to CSV
    metrics_df = pd.DataFrame([metrics])
    metrics_file = os.path.join(args.output_path, f"{args.model}_metrics.csv")
    metrics_df.to_csv(metrics_file, index=False)
    print(f"Metrics saved to: {metrics_file}")

# ------------------------
# 5. Entry Point
# ------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_path", 
        default="data/loan_default_selected_features_clean.csv", 
        help="Path to input CSV file"
    )
    parser.add_argument(
        "--model", 
        default="xgboost", 
        choices=["xgboost", "logreg", "random_forest"], 
        help="Model to train"
    )
    parser.add_argument(
        "--output_path", 
        default="models", 
        help="Directory to save model and metrics"
    )
    args = parser.parse_args()

    main(args)