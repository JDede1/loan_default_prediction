## 💻 Devcontainer / Codespaces

A `.devcontainer/devcontainer.json` is included for reproducible setup in **Codespaces** (or locally with VS Code + Remote Containers).

It ensures:

* `gcloud` CLI installed  
* `Terraform 1.13.1` installed  
* `git-lfs` installed (fixes GitHub push issues)  
* `git` installed inside containers (fixes MLflow Git SHA warnings)  
* Python deps auto-installed from `requirements.txt` + `requirements-dev.txt`  

### ✅ On container start

Authentication is bootstrapped automatically using your service account key:

```bash
gcloud auth activate-service-account --key-file=keys/gcs-service-account.json
gcloud config set project loan-default-mlops
````

→ This runs automatically, so you don’t need to re-run these commands manually every time.

### ⚠️ Notes & Gotchas

* **No Docker-in-Docker (DinD):**
  Codespaces already ships with Docker. We do **not** install the `docker-in-docker` feature to avoid conflicts.

* **Terraform usage inside Codespaces:**
  Run Terraform via the provided Make targets (`make terraform-init`, `make terraform-apply`, etc.). These commands use the dockerized `terraform` container with your GCP service account mounted.

* **Permissions for artifacts/logs:**
  If you see `Permission denied writing /opt/airflow/artifacts/...` in Airflow logs, run:

  ```bash
  make fix-perms
  ```

  This ensures Airflow tasks can write directly to mounted volumes.

* **Secrets:**
  Do **not** commit `.env` or `keys/gcs-service-account.json`. Instead:

  * Use `.env.example` as a template.
  * Place your real GCP service account key at `keys/gcs-service-account.json` (gitignored).
  * Docker Compose mounts it into containers at `/opt/airflow/keys/gcs-service-account.json`.


### 🧪 Quick sanity check

From inside your Codespace terminal:

```bash
gcloud auth list
gcloud config list project
terraform -v
git --version
```

You should see:

* Active SA account
* `loan-default-mlops` as the configured project
* Terraform `1.13.1`
* A valid Git version
---

