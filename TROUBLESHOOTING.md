# Troubleshooting Guide

This document lists common issues encountered during development and deployment, with the **exact error messages** and the fixes that resolved them.

---

## 🔑 Environment & Dependencies

**Issue 1: MLflow dependency mismatch**

```
ValueError: XGBoost version mismatch between training (3.0.4) and serving (1.7.6).
```

✅ **Fix:** Pin aligned versions in `requirements.serve.txt`.

---

**Issue 2: Missing requirements file**

```
FileNotFoundError: [Errno 2] No such file or directory: '/opt/airflow/requirements.serve.txt'
```

✅ **Fix:** Updated `Dockerfile.airflow` to copy the missing file.

---

**Issue 3: Airflow dependency conflict**

```
pkg_resources.ContextualVersionConflict: google-cloud-storage==2.15.0 is incompatible with apache-airflow constraints.
```

✅ **Fix:** Downgraded to a compatible `google-cloud-storage` version.

---

## 🐳 Docker, Volumes & Permissions

**Issue 4: Permission denied on logs/artifacts**

```
PermissionError: [Errno 13] Permission denied: '/opt/airflow/logs/scheduler.log'
```

✅ **Fix:**

* Run `make fix-perms`.
* Pre-create directories in Dockerfile with correct ownership.

---

**Issue 5: UID/GID mismatch**

```
airflow-webserver | OSError: [Errno 13] Permission denied: '/opt/airflow/logs'
```

✅ **Fix:** Set `AIRFLOW_UID=1000` in `.env` to match Codespaces host.

---

**Issue 6: Disk space exhaustion**

```
OSError: [Errno 28] No space left on device
```

✅ **Fix:**

* Run `make clean-disk`.
* Aggressive cleanup with `docker system prune -a -f --volumes`.

---

## 🌬️ Airflow

**Issue 7: Airflow UI not reachable**

```
ModuleNotFoundError: No module named 'airflow'
```

✅ **Fix:** Avoid overwriting Airflow dependencies; re-install pinned requirements.

---

**Issue 8: Admin user not created**

```
airflow-webserver | WARNING - Admin user not found
```

✅ **Fix:** Run `create_airflow_user.sh` during `airflow-init`.

---

**Issue 9: Scheduler crash (stale PID file)**

```
OSError: [Errno 98] Address already in use
airflow-scheduler.pid already exists
```

✅ **Fix:** Run `make reset-logs` to clear stale PID files.

---

## 📊 MLflow

**Issue 10: Serving container crash**

```
mlflow.exceptions.RestException: RESOURCE_DOES_NOT_EXIST: Registered Model 'loan_default_model' not found
```

✅ **Fix:** Bootstrap step to train + register a dummy model before starting Serve.

---

**Issue 11: Artifact path inconsistencies**

```
mlflow.exceptions.MlflowException: Invalid artifact location: /tmp/mlruns
```

✅ **Fix:** Standardized artifact paths → use mounted volumes + GCS bucket.

---

**Issue 12: CI/CD MLflow permission error**

```
PermissionError: [Errno 13] Permission denied: '/opt/airflow/mlruns/0/meta.yaml'
```

✅ **Fix:** Added `fix-mlflow-runs` service in `docker-compose.yaml`.

---

## ⚙️ CI/CD

**Issue 13: Integration test failure (Serve not reachable)**

```
requests.exceptions.ConnectionError: HTTPConnectionPool(host='serve', port=5001): Max retries exceeded with url: /invocations
```

✅ **Fix:** Ensure tests run inside same Docker network; start Serve before integration tests.

---

**Issue 14: Batch prediction test failure**

```
pandas.errors.EmptyDataError: No columns to parse from file: '/opt/airflow/data/batch_input.csv'
```

✅ **Fix:** Add dummy dataset in `data/`; validate schema in test logic.

---

**Issue 15: Makefile error**

```
Makefile:278: *** missing separator.  Stop.
```

✅ **Fix:** Use tabs, not spaces; moved Python code into `scripts/export_env_vars.py`.

---

## 📦 Data & Monitoring

**Issue 16: GCS credentials error**

```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials
```

✅ **Fix:**

* Place service account at `keys/gcs-service-account.json`.
* Ensure correct permissions: `chmod 644`.

---

**Issue 17: Monitoring DAG missing predictions**

```
ValueError: ❌ No predictions found. Run batch_prediction_dag first.
```

✅ **Fix:** Add `LATEST_PREDICTION_PATH` Airflow variable + fallback marker in `airflow/artifacts/latest_prediction.json`.

---

**Issue 18: Evidently version mismatch**

```
ImportError: cannot import name 'BaseModel' from 'pydantic'
```

✅ **Fix:** Harmonized Evidently version across `requirements.txt` and `requirements-monitoring.txt` based on pydantic compatibility.

---

## 🔄 Root Causes

The recurring causes behind most issues:

1. **Dependency drift** → between training, serving, monitoring.
2. **Permissions & UID mismatch** → host vs container ownership.
3. **Path inconsistencies** → artifacts, mlruns, env vars not standardized.
4. **Airflow bootstrap reliability** → user creation, PID handling, DB init.

---

