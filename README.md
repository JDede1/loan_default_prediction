# LendingClub Loan Default Prediction – MLOps Capstone Project

This is an end-to-end machine learning system developed as part of the [MLOps Zoomcamp](https://github.com/DataTalksClub/mlops-zoomcamp) Capstone.

The goal is to predict whether a loan will default based on borrower attributes, using a production-grade ML pipeline with experiment tracking, versioned model registry, Dockerized environments, and REST API model deployment.

---

## Problem Statement

Financial platforms like LendingClub face risk when issuing personal loans. This project builds a model to predict **loan default vs. full repayment** based on borrower and loan features.

* **Type**: Binary Classification
* **Target**: `loan_status` (`1` = default, `0` = fully paid)
* **Challenge**: Imbalanced classes (\~20% default rate)

---

## Project Structure

```
loan_default_prediction/
├── data/                    # Cleaned dataset (CSV)
├── mlruns/                  # MLflow logs, artifacts, and model registry
├── notebooks/               # EDA, cleaning, experiments
│   ├── data_preparation.ipynb
│   ├── train_and_compare.ipynb
│   └── train_pipeline_experiments.ipynb
├── src/                     # Training logic
│   ├── train.py
│   ├── train_and_compare.py
│   └── train_with_mlflow.py
├── sample_input.json        # Sample input for prediction API
├── test_prediction.py       # Python client to test deployed model
├── Dockerfile               # For model training image
├── Dockerfile.serve.custom  # For model serving image
├── requirements-docker.txt  # Docker dependency pinning (training + serving)
├── requirements.txt         # Local development dependencies
└── README.md
```

---

## Tech Stack

| Area                     | Tools Used                       |
| ------------------------ | -------------------------------- |
| Language                 | Python 3.10                      |
| ML Libraries             | scikit-learn, XGBoost            |
| Data Handling            | pandas, numpy                    |
| Tracking                 | MLflow (experiments + registry)  |
| Deployment               | MLflow Model Server + Docker     |
| Orchestration (upcoming) | Prefect, Airflow (optional)      |
| Monitoring (upcoming)    | Evidently, WhyLabs (optional)    |
| CI/CD (upcoming)         | GitHub Actions, Makefile         |
| Environment Mgmt         | Docker, pip freeze, WSL (Ubuntu) |

---

## Sprint-by-Sprint Progress

| Sprint   | Summary                                               |
| -------- | ----------------------------------------------------- |
| **1**    | Problem understanding, dataset definition             |
| **2**    | Data cleaning, feature engineering                    |
| **3**    | EDA, skew correction, rare features                   |
| **4**    | Feature selection and importance                      |
| **5**    | Model training (XGBoost, LogReg, RF), evaluation      |
| **6**    | Training and serving pipelines with Docker and MLflow |
| **7–10** | *Planned*: Orchestration, Monitoring, CI/CD           |

---

## How to Train Models

### Option 1: Basic Training (local, no tracking)

```bash
python src/train.py --model xgboost
```

Creates:

* `models/xgboost_model.pkl`
* `models/xgboost_metrics.csv`

### Option 2: MLflow-Tracked Training with Registry (inside Docker)

```bash
docker run --rm \
  -v ${PWD}/mlruns:/app/mlruns \
  -v ${PWD}/data:/app/data \
  loan-default-trainer
```

Creates:

* Registered model: `loan_default_model`
* MLflow run in: `mlruns/`
* Aliased version: `staging`

---

## Model Deployment

### Build the serving image:

```bash
docker build -f Dockerfile.serve.custom -t loan-default-serving-custom .
```

### Serve the registered model (MLflow):

```bash
docker run --rm -p 5001:5000 \
  -v $(pwd)/mlruns:/app/mlruns \
  -e MLFLOW_TRACKING_URI=file:/app/mlruns \
  loan-default-serving-custom \
  mlflow models serve -m "models:/loan_default_model@staging" --no-conda --host 0.0.0.0
```

---

## Test the API

### Sample input format (`sample_input.json`)

```json
{
  "inputs": [
    {
      "loan_amnt": 3600.0,
      "debt_settlement_flag_Y": 0,
      "term": 3.6109,
      "issue_year": 2015,
      "int_rate": 13.99,
      "grade": 3,
      "total_rev_hi_lim": 9.13,
      "revol_bal": 7.92,
      "dti": 1.93,
      "total_bc_limit": 7.78,
      "fico_range_low": 6.51,
      "bc_open_to_buy": 7.31,
      "annual_inc": 10.91,
      "tot_cur_bal": 11.88,
      "avg_cur_bal": 9.93,
      "mo_sin_old_rev_tl_op": 4.85,
      "revol_util": 29.7,
      "total_bal_ex_mort": 8.95,
      "bc_util": 37.2,
      "mo_sin_old_il_acct": 148.0
    }
  ]
}
```

### Run the client script:

```bash
python test_prediction.py
```

Expected output:

```
Status Code: 200
Response: {"predictions": [0]}
```

---

## Reproducibility Checklist

* [x] Training and serving environments are pinned in `requirements-docker.txt`
* [x] MLflow used to track runs and register models
* [x] Model served via Dockerized MLflow API
* [x] Sample input and prediction script included
* [x] Runs in WSL or Linux environments for portability
* [x] Model deployment returns valid responses from JSON inputs

---

## Future Improvements (Sprint 7–10)

* [ ] Add Prefect or Airflow pipeline orchestration
* [ ] Set up GitHub Actions for CI/CD
* [ ] Add automated retraining triggers
* [ ] Include monitoring dashboard with Evidently or WhyLabs
* [ ] Unit tests, integration tests, and code linting

---

## Acknowledgments

This project was built as part of the **DataTalksClub MLOps Zoomcamp**.
Special thanks to the instructors and community for their guidance and support.

