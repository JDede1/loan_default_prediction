## 💻 Devcontainer / Codespaces

A `.devcontainer/devcontainer.json` is included for reproducible setup in **Codespaces** (or locally with VS Code + Remote Containers).

It ensures:

* `gcloud` CLI installed
* `Terraform 1.13.1` installed
* `git-lfs` installed (fixes GitHub push issues)
* Python deps auto-installed

On container start:

```bash
gcloud auth activate-service-account --key-file=keys/gcs-service-account.json
gcloud config set project loan-default-mlops
```

→ This runs automatically, so you don’t need to re-run these commands manually every time.

---
