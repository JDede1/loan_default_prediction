# 🧠 ML Model Training Scripts

This folder contains all training scripts used in the LendingClub Loan Default Prediction Project. Each script serves a different purpose in the MLOps lifecycle — from experimentation to production tracking and model registry.

---

## Files Overview

### 1. `train_and_compare.py`
- Purpose: Baseline model comparison

- What it does:
  - Trains Logistic Regression, Random Forest, and XGBoost
  - Prints AUC, F1, Precision, Recall
  - Plots comparison chart
- Use during: **Model Benchmarking**

---

### 2. `train.py`
- Purpose: Modular production-ready training script

- What it does:
- Loads cleaned dataset
- Trains a selected model (via `--model` argument)
- Saves model as `.pkl` and metrics as `.csv`
- Use during: **Training Pipeline**

**Example usage:**
`python src/train.py --model xgboost`

---

### 3.` train_with_mlflow.py`
- Purpose: Full MLflow experiment tracking + model registry

- What it does:
- Tracks parameters, metrics, and model artifacts with MLflow
- Registers the trained model to MLflow Model Registry
- Assigns a stage (e.g. "Staging", "Production")
- Use during: Sprint 7 - Experiment Tracking & Model Registry

**Example usage:**
`python src/train_with_mlflow.py --model_name loan_default_model --stage Staging`