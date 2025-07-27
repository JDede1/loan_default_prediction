# LendingClub Loan Default Prediction

## Problem Statement

LendingClub is a peer-to-peer lending platform where applicants can apply for personal loans. The goal of this project is to build a machine learning model that can **predict whether a borrower will default** on their loan based on their financial and application data.

This is a **binary classification** problem, where the target variable is:
- `1`: Defaulted or Charged-off
- `0`: Fully paid

## Objectives

- Perform exploratory data analysis (EDA) and feature engineering
- Train ML models and track experiments with MLflow
- Build a reproducible training pipeline
- Deploy the model (web API or batch inference)
- Monitor model performance in production
- Apply MLOps best practices: CI/CD, testing, containerization, reproducibility, cloud

## Reason for the project

Predicting loan defaults helps financial institutions:
- Minimize financial risk
- Improve credit decisions
- Identify high-risk applicants earlier in the process

## Tools & Tech Stack

- **Data**: LendingClub loan data
- **Modeling**: scikit-learn, XGBoost
- **Experiment Tracking**: MLflow
- **Pipeline Orchestration**: Prefect
- **Deployment**: FastAPI or batch pipeline + Docker
- **Monitoring**: Evidently, custom metrics, logging
- **Infrastructure**: GitHub Codespaces, optional Terraform, Docker, CI/CD

## Project Structure

loan-default-prediction/
├── data/ # Raw and processed data
├── notebooks/ # EDA and prototyping notebooks
├── src/ # Source code: training, preprocessing, inference
│ └── config/ # Configuration files
├── tests/ # Unit and integration tests
├── docker/ # Dockerfiles and container setup
├── .github/workflows/ # CI/CD workflows
├── requirements.txt # Python dependencies
├── environment.yml # Conda environment (optional)
├── README.md # Project overview
