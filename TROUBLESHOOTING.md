## 🛠 Troubleshooting

Common issues and fixes when running the pipeline:


### 1. **Serve container fails with `RESOURCE_DOES_NOT_EXIST`**

**Error:**
```

mlflow\.exceptions.RestException: RESOURCE\_DOES\_NOT\_EXIST: Registered Model with name=loan\_default\_model not found

```

**Cause:** Serving container started **before** a model exists in the MLflow Registry.

**Fix:**
1. Start core services: `make start`
2. Train a model via Airflow DAG `train_pipeline_dag`
3. Confirm in MLflow UI → *Models* → `loan_default_model`
4. Start serving: `make start-serve` (health: `curl -sS http://localhost:5001/ping`)


### 2. **Permission denied writing artifacts (plots, reports)**

**Error in Airflow logs:**
```

⚠️ Permission denied writing /opt/airflow/artifacts/feature\_importance.png

````

**Cause:** Container doesn’t have write permissions on mounted `artifacts/`.

**Fix:**
* Run `make fix-perms` (new Make target to reset ownership and perms).
* Or, inside Codespaces, run manually:
  ```bash
  sudo chmod -R 777 artifacts/ airflow/artifacts/ airflow/logs/ mlruns/
````

This ensures Airflow tasks can write plots and reports directly to the mounted artifact dirs, instead of falling back to `/tmp/artifacts`.

### 3. **MLflow Git SHA warnings**

**Error in logs:**

```
WARNING mlflow.utils.git_utils: Failed to import Git (the Git executable is probably not on your PATH)...
```

**Cause:** MLflow tries to capture the Git commit hash for reproducibility, but `git` wasn’t available in the container.

**Fix:**
We now install `git` in `Dockerfile.airflow`. Rebuild your containers:

```bash
make stop
make start
```

### 4. **MLflow requirements inference warnings**

**Error in logs:**

```
WARNING mlflow.utils.environment: Encountered an unexpected error while inferring pip requirements...
```

**Cause:** MLflow tries to auto-infer dependencies from the model, which may fail or be incomplete.

**Fix:**
We now provide a pinned `requirements.serve.txt` when logging models. This ensures serving uses the exact same dependency versions as training, avoiding inference issues.

### 5. **GCS access errors (403 / denied)**

**Error:**

```
google.api_core.exceptions.Forbidden: 403 ... does not have storage.objects.get access
```

**Fix:**

* Ensure your service account has IAM:

  * `roles/storage.objectAdmin` (read/write)
  * Or minimally `roles/storage.objectViewer` (read-only)
* Verify key is mounted correctly:
  `keys/gcs-service-account.json` → `/opt/airflow/keys/gcs-service-account.json`

### 6. **Airflow webserver won’t start (healthcheck fails)**

**Fix:**

* Run `make troubleshoot` to tail logs.
* Ensure no stale PID files:

  ```bash
  rm -f airflow/airflow-webserver.pid airflow/airflow-scheduler.pid
  ```
* Rebuild clean:

  ```bash
  make stop
  make start --fresh
  ```

### 7. **Integration tests fail in CI but pass locally**

**Cause:** CI may start `serve` before model exists.

**Fix:**

* Restrict CI to lint + unit tests (`ci.yml`).
* Run integration only on demand (`ci-integration.yml`).
* Locally, run:

  ```bash
  make start
  # train via Airflow
  make start-serve
  make integration-tests
  ```

### 8. **Git LFS blocking pushes**

**Error:**

```
This repository is configured for Git LFS but 'git-lfs' was not found on your path
```

**Fix:**

* Install git-lfs inside Codespaces (already automated in `.devcontainer`).
* Or disable LFS hooks if not using LFS:

  ```bash
  rm -f .git/hooks/pre-push .git/hooks/post-commit
  ```

🔑 **Tip:** When in doubt, run:

```bash
make troubleshoot
docker compose -f airflow/docker-compose.yaml logs -f
```

This will surface most container-level issues.

### 9) “Docker-in-Docker” feature fails in Codespaces

**Why**
Codespaces already provides Docker—no need for DinD.

**Fix**

* Ensure `.devcontainer/devcontainer.json` does **not** include `docker-in-docker` feature.
* Use the provided devcontainer that installs `gcloud`, Terraform, and `git-lfs` only.

---
