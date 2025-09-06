.PHONY: install lint format test start stop start-serve stop-serve troubleshoot \
	terraform-init terraform-plan terraform-apply terraform-destroy integration-tests \
	fix-perms bootstrap clean-disk clean-light stop-hard backup-airflow restore-airflow \
	reset restart-webserver restart-serve

# === Python/Dev Setup ===
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

lint:
	flake8 src tests

format:
	black src tests
	isort src tests

test:
	pytest -v tests

# === Airflow / MLflow Core ===
start:
	cd airflow && ./start_all.sh

stop:
	cd airflow && ./stop_all.sh

# Stop + deep clean (use when disk pressure is high)
stop-hard: stop
	-$(MAKE) backup-airflow
	docker system prune -a -f --volumes
	# Clear local logs/runs/caches
	sudo rm -rf airflow/logs/* mlruns/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	df -h /

# === Model Serving ===
start-serve:
	cd airflow && ./start_serve.sh

stop-serve:
	cd airflow && ./stop_serve.sh

troubleshoot:
	cd airflow && ./troubleshoot.sh

# === Terraform (GCP Infrastructure) ===
terraform-init:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform init"

terraform-plan:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform plan"

terraform-apply:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform apply -auto-approve"

terraform-destroy:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform destroy -auto-approve"

# === Integration Tests (run inside webserver container, ensure serve is up) ===
integration-tests:
	docker compose -f airflow/docker-compose.yaml up -d serve
	docker compose -f airflow/docker-compose.yaml run --rm \
		--workdir /opt/airflow \
		--entrypoint "" \
		-e PYTHONPATH=/opt/airflow \
		-e RUN_INTEGRATION_TESTS=1 \
		-e MLFLOW_TRACKING_URI=http://mlflow:5000 \
		-e GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/keys/gcs-service-account.json \
		webserver pytest tests -m integration -v
	docker compose -f airflow/docker-compose.yaml down --remove-orphans

# === Permissions (prevent artifact/log write failures) ===
fix-perms:
	# Ensure local dirs exist for bind mounts
	mkdir -p artifacts airflow/artifacts airflow/tmp mlruns airflow/logs
	# Codespaces has sudo; this fixes container write perms to mounted volumes
	sudo chmod -R 777 artifacts airflow/artifacts airflow/tmp mlruns airflow/logs
	# Pre-create subfolder expected by Airflow
	mkdir -p airflow/logs/dag_processor_manager

# === One-shot setup for fresh envs (optional) ===
bootstrap:
	# Don't overwrite an existing .env; create from example if missing
	[ -f .env ] || cp -n .env.example .env || true
	$(MAKE) install
	$(MAKE) fix-perms
	$(MAKE) start

# === Emergency disk cleanup (Codespaces / Docker) ===
clean-disk:
	# Remove unused Docker images, containers, volumes, networks, and build cache
	docker system prune -a -f --volumes
	# Clean up Airflow logs, MLflow runs, and Python caches
	sudo rm -rf airflow/logs/* mlruns/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	# Show free disk space after cleanup
	df -h /

# === Light, routine cleanup (safe) ===
clean-light:
	docker container prune -f
	docker image prune -f
	# Keep volumes; just trim local logs and pyc caches
	sudo rm -rf airflow/logs/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	df -h /

# === Backup & Restore Airflow Variables/Connections ===
backup-airflow:
	# Export Airflow Variables and Connections to JSON files
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables export /opt/airflow/variables.json || true
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow connections export /opt/airflow/connections.json || true
	# Copy them out of the container to the host
	docker cp airflow-webserver:/opt/airflow/variables.json ./airflow/variables.json || true
	docker cp airflow-webserver:/opt/airflow/connections.json ./airflow/connections.json || true
	@echo "✅ Airflow Variables and Connections backed up to ./airflow/"

restore-airflow:
	# Copy JSON backups into the container
	docker cp ./airflow/variables.json airflow-webserver:/opt/airflow/variables.json || true
	docker cp ./airflow/connections.json airflow-webserver:/opt/airflow/connections.json || true
	# Import them into Airflow
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables import /opt/airflow/variables.json || true
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow connections import /opt/airflow/connections.json || true
	@echo "✅ Airflow Variables and Connections restored"

# === New Convenience Targets ===
reset:
	docker compose -f airflow/docker-compose.yaml down -v
	docker compose -f airflow/docker-compose.yaml build --no-cache
	docker compose -f airflow/docker-compose.yaml up airflow-init
	docker compose -f airflow/docker-compose.yaml up -d postgres mlflow scheduler webserver
	@echo "✅ Reset complete. Airflow UI → http://localhost:8080 | MLflow UI → http://localhost:5000"

restart-webserver:
	docker compose -f airflow/docker-compose.yaml restart webserver
	@echo "🔄 Webserver restarted. Check logs with: docker compose -f airflow/docker-compose.yaml logs -f webserver"

restart-serve:
	docker compose -f airflow/docker-compose.yaml restart serve
	@echo "🔄 Serving container restarted. Health check: curl -s http://localhost:5001/ping"
