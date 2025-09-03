## 🔐 Secrets & Safety

**Never commit secrets.** Use templates and mounts; keep real values local.

### What to keep out of Git

* Real `.env` (commit **`.env.example`** only)
* `keys/gcs-service-account.json` (gitignored)
* Terraform state & tfvars (`infra/terraform/.terraform/`, `terraform.tfstate*`, `terraform.tfvars`)
* Runtime artifacts/logs (`airflow/logs/`, `airflow/mlruns/`, `artifacts/`, root `mlruns/`)

### Safe templates

* **`.env.example`** — placeholders for all required env vars (Airflow keys, project/bucket, MLflow URIs, SMTP/Slack if used)
* **`infra/terraform/terraform.tfvars.example`** — placeholders for `project_id`, `region`, `bucket_name`

### Rotation (if something leaks)

* **Airflow**: generate new `AIRFLOW__CORE__FERNET_KEY` and `AIRFLOW__WEBSERVER__SECRET_KEY`
* **Slack**: create a new webhook; delete the old
* **Gmail App Password (SMTP)**: revoke and create a new one
* **GCP Service Account**: create a new key, delete the old key ID
* Update compose/`.env`, rebuild, and redeploy

### Principle of least privilege

* Grant **roles/storage.objectAdmin** to the runtime service account on the bucket.
* For production, prefer **GCP Secret Manager** over JSON key files

### Scanning & pre-commit

Add secret scanning to prevent accidental commits:

* **Pre-commit**: `gitleaks` (or `trufflehog`) hook
* CI step to run the scanner on PRs

Example `.pre-commit-config.yaml`:

```yaml
repos:
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v4.6.0
  hooks:
    - id: check-added-large-files
    - id: end-of-file-fixer
    - id: trailing-whitespace

- repo: https://github.com/gitleaks/gitleaks
  rev: v8.18.4
  hooks:
    - id: gitleaks
```

Enable:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```
---

---
## 🧑‍💻 Development & Contribution

We welcome contributions to improve the project.
Follow the guidelines below to ensure consistency, code quality, and smooth collaboration.

### Development Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/JDede1/loan_default_prediction.git
cd loan_default_prediction

# Install core + dev dependencies
make install
```

### Code Quality

The project enforces **linting, formatting, and type checks**:

```bash
# Format code
make format

# Lint code
make lint

# Run tests
make test
```

### Tools Used

* **Black** → Python code formatting
* **isort** → Import sorting
* **Flake8** → Style guide enforcement
* **Mypy** → Static type checking
* **Pytest** → Unit & integration testing


### Git Workflow

1. **Create a feature branch**

   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Commit changes with clear messages**

   ```bash
   git commit -m "Add feature: X with explanation"
   ```

3. **Push branch & open PR**

   ```bash
   git push origin feature/my-new-feature
   ```

4. **PR Review & Merge** → Code is reviewed before merging into `main`.

### Testing

* Unit tests → `tests/test_utils.py`
* Integration tests → `tests/test_prediction_integration.py` & `tests/test_batch_prediction_integration.py`

To run integration tests locally:

```bash
RUN_INTEGRATION_TESTS=1 pytest -m integration -v
```

### Contribution Guidelines

* Write clear commit messages (conventional commits encouraged).
* Add/update tests for new features.
* Ensure `make lint format test` passes before submitting PR.
* Document new features in the **README** or inline code comments.
---