# Security and Contributing Guidelines

## 🔒 Security Practices

We take security seriously in this project. Please follow these guidelines when working with the repo:

* **Secrets Management**

  * Do **not** commit `.env` files, service account keys, or credentials to git.
  * All secrets are ignored via `.gitignore` (`.env`, `keys/`, `airflow/keys/`).
  * Use the provided `.env.example` as a template.

* **Service Accounts & IAM**

  * Service accounts should be created with **least privilege** roles.
  * Example roles required:

    * `roles/storage.admin`
    * `roles/aiplatform.admin`
    * `roles/artifactregistry.admin`
    * `roles/run.admin`

* **Dependency Security**

  * Dependencies are pinned in `requirements.txt` and environment-specific files (`requirements-dev.txt`, etc.).
  * Run `pip install --upgrade` cautiously and re-test before committing changes.

* **Vulnerability Reporting**

  * If you discover a security issue, **do not open a public GitHub issue**.
  * Instead, contact the maintainers directly at:
    📧 **\[[your-email@example.com](mailto:your-email@example.com)]**

---

## 🤝 Contributing Guidelines

We welcome contributions! Please follow these practices to ensure smooth collaboration:

### 1. Fork & Branch

* Fork the repo and create a feature branch:

  ```bash
  git checkout -b feature/my-new-feature
  ```

### 2. Development Setup

* Install dependencies:

  ```bash
  make install
  ```
* Copy `.env.example` → `.env` and configure environment variables.

### 3. Code Style

* Format code using:

  ```bash
  make format
  ```
* Check style compliance:

  ```bash
  make check-format
  make lint
  ```
* Type check:

  ```bash
  mypy src
  ```

### 4. Testing

* Run unit tests:

  ```bash
  make test
  ```
* Run integration tests (requires Docker stack running):

  ```bash
  make integration-tests
  ```

### 5. Pull Requests

* Ensure your PR passes **all checks** (lint, format, unit + integration tests).
* Provide a **clear description** of the change.
* Reference related issues where applicable.

---

✅ With these practices, we keep the project **secure, consistent, and maintainable**.

---

