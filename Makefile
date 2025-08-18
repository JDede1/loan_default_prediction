.PHONY: install lint format test start stop terraform-init terraform-plan terraform-apply terraform-destroy integration-tests

# === Python/Dev Setup ===
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

lint:
	flake8 src tests

format:
	black src tests

test:
	pytest -v tests

# === Airflow / MLflow / Model Serving ===
start:
	cd airflow && ./start_all.sh

stop:
	cd airflow && ./stop_all.sh

# === Terraform (GCP Infrastructure) ===
terraform-init:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform init"

terraform-plan:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform plan"

terraform-apply:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform apply -auto-approve"

terraform-destroy:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform destroy -auto-approve"

# === Integration Tests (run inside webserver container) ===
integration-tests:
	docker compose -f airflow/docker-compose.yaml run --rm \
		--workdir /opt/airflow \
		--entrypoint "" \
		-e PYTHONPATH=/opt/airflow \
		-e RUN_INTEGRATION_TESTS=1 \
		-e MLFLOW_TRACKING_URI=http://mlflow:5000 \
		-e GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/keys/gcs-service-account.json \
		webserver pytest tests -m integration -v
