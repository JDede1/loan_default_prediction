.PHONY: install lint format test start stop terraform-init terraform-plan terraform-apply terraform-destroy

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

