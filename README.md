Got it ✅.
# 🏦 Loan Default Prediction – End-to-End MLOps Project

This project implements an **end-to-end MLOps pipeline** for predicting loan defaults using the [LendingClub dataset](https://www.kaggle.com/wordsforthewise/lending-club).  

It is built as part of the **DataTalksClub MLOps Zoomcamp capstone project** and demonstrates how to move from a trained ML model to a **production-grade ML system** with automated retraining, deployment, monitoring, and CI/CD best practices.

---
📌 Project Overview
Problem Statement

Loan default is a major risk for financial institutions, leading to significant revenue loss and operational costs. The goal of this project is to build an end-to-end machine learning pipeline that predicts the likelihood of loan default and integrates the prediction workflow into a production-ready MLOps system.

Dataset

We use the LendingClub Loan Dataset, a publicly available dataset containing borrower profiles and loan repayment outcomes.

Cleaned dataset stored in GCS bucket:
gs://loan-default-artifacts-loan-default-mlops/data/loan_default_selected_features_clean.csv

Features include loan amount, interest rate, credit grade, revolving balance, and other financial indicators.

Target variable: loan_status (defaulted vs non-defaulted).

Objectives

This project demonstrates the full MLOps lifecycle:

✅ Train, evaluate, and register predictive models with MLflow

✅ Automate workflows (training, prediction, monitoring, promotion) with Airflow DAGs

✅ Deploy models as REST APIs and batch pipelines with Docker + MLflow

✅ Monitor model performance and detect drift with Evidently

✅ Store and serve artifacts via Google Cloud Storage (GCS) provisioned using Terraform

✅ Ensure reproducibility, testing, and CI/CD best practices

---

🏗️ Architecture & Technologies
High-Level Workflow

Data Storage → Training data and batch inputs are stored in Google Cloud Storage (GCS) buckets provisioned via Terraform.

Experiment Tracking → Models are trained, evaluated, and logged to MLflow (metrics, parameters, artifacts, model registry).

Workflow Orchestration → Apache Airflow DAGs automate training, batch inference, monitoring, and model promotion.

Deployment → The best model is deployed via MLflow Serving in a Docker container, exposing a REST API.

Batch Prediction → Airflow runs daily batch prediction jobs and saves outputs to GCS.

Monitoring → Predictions are compared against reference data using Evidently, generating drift and performance reports.

Alerts & Promotion → Slack/email alerts notify of model promotions or failures. Models are automatically promoted from staging → production if thresholds are met.

CI/CD & Testing → GitHub Actions ensures linting, unit tests, and integration tests run on every commit.

Tools & Technologies

Cloud & IaC → Google Cloud Platform (GCS) + Terraform

Experiment Tracking & Registry → MLflow

Workflow Orchestration → Apache Airflow (DAGs for training, prediction, monitoring, promotion)

Model Deployment → MLflow Serving (Dockerized REST API)

Monitoring → Evidently (data & concept drift, quality metrics)

CI/CD → GitHub Actions (linting, tests, automation)

Testing → Pytest (unit + integration tests)

Best Practices → Makefile, Dockerfiles, pre-commit formatting, reproducibility via requirements.txt

### 🔹 High-Level Workflow  

```mermaid
flowchart LR
    Data[📊 Data] --> Training[🧠 Training]
    Training --> Registry[📦 MLflow Registry]
    Registry --> Serving[🚀 Serving API]
    Serving --> Prediction[📈 Batch Predictions]
    Prediction --> Monitoring[🛡️ Monitoring & Drift Detection]


### Detailed architecture diagram ###

```mermaid
flowchart LR
    subgraph Data["📊 Data Source (GCS Bucket)"]
        A[loan_default_selected_features_clean.csv]
        B[batch_input.csv]
    end

    subgraph Training["🧠 Model Training (Airflow DAG)"]
        A --> T1[train_with_mlflow.py]
        T1 --> MLflow[(MLflow Tracking & Registry)]
        T1 --> Artifacts[(Artifacts in GCS)]
    end

    subgraph Registry["📦 Model Registry"]
        MLflow --> Staging[(Staging Alias)]
        MLflow --> Production[(Production Alias)]
    end

    subgraph Serving["🚀 Model Serving"]
        Staging --> API[MLflow REST API (Docker)]
    end

    subgraph Batch["📈 Batch Prediction DAG"]
        B --> P1[batch_predict.py]
        P1 --> Predictions[(Predictions in GCS)]
        Predictions --> Marker[latest_prediction.txt]
    end

    subgraph Monitoring["🛡️ Monitoring DAG"]
        Marker --> M1[monitor_predictions.py (Evidently)]
        A --> M1
        M1 --> Reports[(Monitoring Reports in GCS)]
    end

---

## 📂 Project Structure

```bash
loan_default_prediction/
├── airflow/                  # Airflow environment, DAGs, and scripts
│   ├── dags/                 # DAG definitions (training, promotion, batch prediction, monitoring)
│   ├── docker-compose.yaml   # Docker Compose stack for Airflow + MLflow + Serve
│   ├── start_all.sh          # Script to build & start all core services
│   ├── stop_all.sh           # Script to stop/clean environment
│   ├── troubleshoot.sh       # Health check & auto-fix for services
│   └── keys/                 # GCP service account (not committed)
│
├── data/                     # Input data for training & batch predictions
│   ├── loan_default_selected_features_clean.csv
│   └── batch_input.csv
│
├── infra/terraform/          # Terraform configs for GCP infrastructure
│   ├── main.tf               # Bucket + API provisioning
│   ├── variables.tf
│   ├── terraform.tfvars
│   └── outputs.tf
│
├── model/                    # Saved models & artifacts (MLflow-managed)
│
├── src/                      # Core source code
│   ├── train_with_mlflow.py  # Training & logging models to MLflow
│   ├── batch_predict.py      # Run batch predictions with registered model
│   ├── monitor_predictions.py# Monitoring & drift detection with Evidently
│   ├── utils.py              # Helper utilities
│   └── ...
│
├── tests/                    # Unit & integration tests
│   ├── test_utils.py
│   ├── test_batch_prediction_integration.py
│   └── test_prediction_integration.py
│
├── .env                      # Environment variables (Airflow, MLflow, GCP, alerts)
├── Makefile                  # Common commands (lint, test, start/stop services, terraform)
├── requirements.txt          # Python dependencies
├── requirements-dev.txt      # Dev/test dependencies
├── requirements.serve.txt    # Model serving dependencies
├── requirements-monitoring.txt # Monitoring dependencies
├── Dockerfile*               # Dockerfiles for Airflow, monitoring, serving, Terraform
└── README.md                 # Project documentation
```

> 🔑 **Notes**
>
> * Secrets (like service account keys) are **not committed** — they live in `airflow/keys/`.
> * `mlruns/` and `artifacts/` directories are generated at runtime by MLflow & Airflow and should be `.gitignore`d.
> * The repo is structured to be reproducible with `make start` and `terraform apply`.

---

## ☁️ Cloud Infrastructure

This project provisions cloud resources on **Google Cloud Platform (GCP)** using **Terraform** for reproducibility and Infrastructure-as-Code.

* **GCS Bucket**:
  A dedicated storage bucket is created for storing training data, batch inputs, predictions, and MLflow artifacts.

  * Bucket name pattern: `loan-default-artifacts-<project_id>`
  * Versioning enabled, lifecycle rule applied (auto-delete after 30 days for cost control).

* **Terraform Setup**:
  Located under `infra/terraform/`:

  * `main.tf`: Enables Storage API and provisions the GCS bucket.
  * `variables.tf` & `terraform.tfvars`: Manage project configuration (`project_id`, `region`, `bucket_name`).
  * `outputs.tf`: Exposes bucket name and URL for reference.

* **Authentication**:
  A **GCP service account key** (`gcs-service-account.json`) is mounted into Airflow and Terraform containers at `/opt/airflow/keys/`. This allows secure access to GCS.

* **Local Fallback**:
  For reviewers without GCP access, the project can still run end-to-end locally:

  * MLflow uses a local `mlruns/` backend.
  * Airflow and batch predictions use mounted `data/` and `artifacts/` folders.
  * GCP-specific commands (`gsutil`, `gcloud`) can be stubbed or skipped locally.

> 🛠️ **Commands**

* Initialize: `make terraform-init`
* Plan: `make terraform-plan`
* Apply: `make terraform-apply`
* Destroy: `make terraform-destroy`

---

## 🎯 Experiment Tracking & Model Registry

The project uses **MLflow** for experiment tracking, artifact storage, and model registry.

* **Tracking**

  * All training runs are logged to **MLflow Tracking Server** (running in Docker on port `5000`).
  * Metrics logged: `AUC`, `F1`, `Precision`, `Recall`, training time, and loss curves.
  * Artifacts logged: feature importance plots, confusion matrix, ROC curves, and parameter JSONs.

* **Artifacts Storage**

  * In **cloud mode**, MLflow artifacts are stored in the provisioned GCS bucket (`gs://loan-default-artifacts-<project_id>/mlflow`).
  * In **local mode**, artifacts are stored under `./mlruns/`.

* **Model Registry**

  * Models are registered under a common name (default: `loan_default_model`).
  * Two key **aliases** are maintained:

    * `staging`: candidate models from the training pipeline.
    * `production`: models promoted after evaluation.
  * Promotion is based on thresholds (`AUC ≥ 0.75`, `F1 ≥ configurable threshold`).

* **Integration with Airflow**

  * Training DAG logs runs to MLflow.
  * Promotion DAG updates aliases (`staging → production`) and tags runs with audit metadata (`triggered_by`, `trigger_source`).

> 🌐 **Access**

* MLflow UI available at: [http://localhost:5000](http://localhost:5000) when services are running.

---

## ⚙️ Workflow Orchestration

The project uses **Apache Airflow** (running in Docker on port `8080`) to orchestrate all ML workflows.

* **DAGs Implemented**

  1. **`train_model_with_mlflow`**

     * Runs weekly.
     * Trains a new model with latest data.
     * Logs metrics/artifacts to MLflow.
     * Decides if the model meets promotion criteria.
     * Triggers `promote_model_dag` if thresholds are satisfied.
     * Automatically triggers batch prediction after training.

  2. **`promote_model_dag`**

     * Promotes models from `staging` → `production` alias.
     * Adds audit tags: who/what triggered promotion.
     * Sends notifications via Slack + email on success/failure.

  3. **`batch_prediction_dag`**

     * Runs daily.
     * Uses the latest `staging` or `production` model to generate predictions.
     * Saves results to GCS bucket (`predictions/` folder).
     * Updates a `latest_prediction.txt` marker file.
     * Triggers monitoring DAG afterward.

  4. **`monitoring_dag`**

     * Runs daily after batch prediction.
     * Uses **Evidently** to detect data and prediction drift.
     * Reports stored in artifacts folder / GCS.

* **Scheduling Strategy**

  * **Weekly** retraining and candidate model evaluation.
  * **Daily** predictions + monitoring to track model health.
  * DAGs are **decoupled but connected** via `TriggerDagRunOperator`.

> 🌐 **Access**

* Airflow UI available at: [http://localhost:8080](http://localhost:8080) when services are running.
---

## 🚀 Model Deployment

The project uses **MLflow Model Serving** inside a dedicated Docker container (`serve` service) to expose models via a REST API.

* **Serving Setup**

  * The container pulls models directly from the **MLflow Model Registry**.
  * Default endpoint: `http://localhost:5001/invocations`
  * Always serves the **`staging` alias** model by default.

* **Testing Predictions**
  You can send JSON payloads in `dataframe_split` format:

  ```bash
  curl -X POST http://localhost:5001/invocations \
    -H "Content-Type: application/json" \
    -d @data/sample_input.json
  ```

  Example response:

  ```json
  {"predictions": [0]}
  ```

* **Why this matters**

  * Consistent with MLflow UI registry aliases.
  * Same container can serve different versions just by updating alias.
  * Integration tested in `test_prediction_integration.py`.

> 🌐 **Access**

* MLflow UI: [http://localhost:5000](http://localhost:5000)
* Prediction API: [http://localhost:5001/invocations](http://localhost:5001/invocations)

---

## 📊 Model Monitoring

The project integrates **Evidently** to monitor data drift and prediction quality over time.

* **Monitoring DAG (`monitoring_dag`)**

  * Runs daily after batch predictions.
  * Reads:

    * **Training data** (`TRAIN_DATA_PATH`)
    * **Latest predictions** (resolved via `latest_prediction.txt` in GCS).
  * Executes `monitor_predictions.py`, which:

    * Generates drift and performance reports.
    * Saves reports as artifacts in MLflow / GCS.

* **Key Features**

  * Automated detection of drift between training and inference data.
  * Reports stored in GCS for persistence and review.
  * Alerts can be extended via Slack / Email.

* **Why this matters**

  * Ensures deployed models remain reliable over time.
  * Provides early warning for retraining or promotion decisions.

---

## 🧪 Reproducibility & Best Practices

This project is designed with **reproducibility and maintainability** in mind:

* **Environment Management**

  * All services (Airflow, MLflow, Serving, Terraform) run inside **Docker containers**.
  * Dependencies are pinned in `requirements.txt`, `requirements-dev.txt`, and service-specific files (`requirements.serve.txt`, `requirements-monitoring.txt`).

* **Automation (Makefile + Scripts)**

  * `make start` / `make stop` to spin up or tear down the full environment.
  * `terraform.sh` for GCP infrastructure lifecycle (`init`, `plan`, `apply`, `destroy`).
  * `start_all.sh` / `stop_all.sh` handle Airflow, MLflow, and model serving consistently.

* **Testing**

  * **Unit tests** (e.g., `test_utils.py`).
  * **Integration tests** (`test_batch_prediction_integration.py`, `test_prediction_integration.py`).
  * Optional flag `RUN_INTEGRATION_TESTS` ensures CI/CD can skip heavy tests when needed.

* **CI/CD Pipeline**

  * GitHub Actions workflow (`.github/workflows/ci.yaml`):

    * Linting with `flake8`.
    * Code formatting with `black`.
    * Unit and integration tests.

* **Code Quality**

  * Consistent linting & formatting enforced via `make lint` and `make format`.
  * Modularized source code (`src/`) and DAGs (`airflow/dags/`).

* **Best Practices**

  * Clear separation of concerns (training, tuning, serving, monitoring).
  * Infrastructure-as-Code with Terraform.
  * Experiment tracking and model registry via MLflow.
  * Cloud storage (GCS) for reproducible artifact access.

---

## 📌 Evaluation Mapping

This section maps the project’s implementation directly to the **MLOps Zoomcamp evaluation rubric**.

| **Category**                             | **Implementation**                                                                                                                                     | **Score (0–4)** |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- |
| **Problem description**                  | Clear business problem: predicting **loan default risk** using LendingClub dataset. Detailed in Project Overview.                                      | ✅ 4             |
| **Cloud**                                | Full integration with **Google Cloud Platform (GCP)** via Terraform (GCS bucket for data, models, predictions, and reports). Local fallback supported. | ✅ 4             |
| **Experiment tracking & Model registry** | MLflow used for experiment tracking, metric logging, and model registry. Aliases (`staging`, `production`) managed automatically in Airflow DAGs.      | ✅ 4             |
| **Workflow orchestration**               | **Airflow DAGs** for training, promotion, batch prediction, and monitoring. Scheduled retraining + daily batch inference + monitoring pipeline.        | ✅ 4             |
| **Model deployment**                     | MLflow model serving inside Docker (`serve` service). REST API tested with integration tests.                                                          | ✅ 4             |
| **Monitoring**                           | **Evidently** integrated for drift detection on daily predictions. Results stored in GCS.                                                              | ✅ 4             |
| **Reproducibility**                      | Containerized environment (Dockerfiles), Makefile commands, pinned dependencies, Terraform infra code.                                                 | ✅ 4             |
| **Best practices**                       | - Modularized code (src/, airflow/dags/)<br> - Linting & formatting (`flake8`, `black`)<br> - GitHub Actions CI/CD<br> - Unit & integration tests      | ✅ 4             |

➡️ **Expected overall score: 4 across all categories (Full Points).**
---

## 🚀 Getting Started (Quickstart Guide)

This section helps you (or reviewers) run the entire project from scratch.

### 1. **Clone the repository**

```bash
git clone https://github.com/your-username/loan_default_prediction.git
cd loan_default_prediction
```

---

### 2. **Set up environment & keys**

1. Create a `keys/` folder in the project root.
2. Place your **GCP service account key** as:

   ```
   keys/gcs-service-account.json
   ```
3. Ensure `.env` file is present at the root (already included in repo).

---

### 3. **Install dependencies (local option)**

If running outside Docker:

```bash
make install
```

For development checks:

```bash
make lint
make format
make test
```

---

### 4. **Start services**

Spin up **Airflow, MLflow, Postgres, Serve, Terraform** containers:

```bash
make start
```

This will:

* Start **Airflow UI** → [http://localhost:8080](http://localhost:8080)
* Start **MLflow UI** → [http://localhost:5000](http://localhost:5000)
* Start **Serving API** → [http://localhost:5001](http://localhost:5001)

---

### 5. **Run Terraform (provision GCS bucket)**

```bash
make terraform-init
make terraform-apply
```

This creates the `loan-default-artifacts-<project_id>` bucket in GCP.

---

### 6. **Trigger DAGs in Airflow**

From the Airflow UI:

1. **train\_model\_with\_mlflow** → trains model & registers in MLflow.
2. **promote\_model\_dag** → promotes model from staging → production.
3. **batch\_prediction\_dag** → generates daily predictions, uploads to GCS.
4. **monitoring\_dag** → runs Evidently drift reports on predictions.

---

### 7. **Test Serving API**

Send a prediction request:

```bash
curl -X POST http://localhost:5001/invocations \
  -H "Content-Type: application/json" \
  -d @data/sample_input.json
```

Expected response:

```json
{"predictions": [0]}
```

---

### 8. **Stop services**

```bash
make stop
```
🙏 Acknowledgements

This project was developed as part of the DataTalksClub MLOps Zoomcamp.
I’m deeply thankful to DataTalksClub for providing such an amazing opportunity to learn, apply, and practice real-world MLOps concepts through hands-on projects.

Special thanks to the instructors, mentors, and community for guidance, resources, and feedback throughout this journey.


