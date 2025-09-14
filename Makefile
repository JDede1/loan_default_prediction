.PHONY: install lint format test start stop down start-core stop-core start-serve stop-serve troubleshoot \
	terraform-init terraform-plan terraform-apply terraform-destroy integration-tests \
	fix-perms reset-logs bootstrap clean-disk clean-light stop-hard backup-airflow restore-airflow \
	reset fresh-reset restart-webserver restart-serve reset-vars verify \
	gcloud-auth build-trainer push-trainer trainer

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
start: fix-perms
	docker compose -f airflow/docker-compose.yaml up -d
	@echo "🌐 Stack started: Airflow → http://localhost:8080 | MLflow → http://localhost:5000 | Serve → http://localhost:5001"

stop:
	docker compose -f airflow/docker-compose.yaml stop
	@echo "🛑 All services stopped (containers paused, volumes/networks preserved)."

down:
	docker compose -f airflow/docker-compose.yaml down
	@echo "🛑 All services stopped and removed (containers + networks)."

# Start/stop only the main stack (postgres, webserver, scheduler, mlflow)
start-core: fix-perms
	docker compose -f airflow/docker-compose.yaml up -d postgres mlflow scheduler webserver
	@echo "🌐 Airflow UI → http://localhost:8080 | MLflow UI → http://localhost:5000"

stop-core:
	docker compose -f airflow/docker-compose.yaml stop postgres mlflow scheduler webserver
	@echo "🛑 Core services stopped."

# Stop + deep clean (use when disk pressure is high)
stop-hard: down
	-$(MAKE) backup-airflow
	docker system prune -a -f --volumes
	sudo rm -rf airflow/logs/* mlruns/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	df -h /

# === Model Serving ===
start-serve:
	docker compose -f airflow/docker-compose.yaml up -d serve
	@echo "🌐 Serve API → http://localhost:5001"

stop-serve:
	docker compose -f airflow/docker-compose.yaml stop serve
	@echo "🛑 Model serving stopped."

# === Troubleshooting (inline from troubleshoot.sh) ===
troubleshoot:
	@echo "🔍 Airflow, MLflow & Serving Troubleshooting Script"
	@docker compose -f airflow/docker-compose.yaml ps
	@ls -ld airflow/logs airflow/artifacts mlruns artifacts 2>/dev/null || true
	@if [ ! -w airflow/logs ] || [ ! -d airflow/logs/dag_processor_manager ]; then \
		echo "🛠 Host logs dir not writable or missing subfolder — running make fix-perms..."; \
		$(MAKE) fix-perms || true; \
	fi
	@for service in $$(docker compose -f airflow/docker-compose.yaml config --services); do \
		status=$$(docker inspect --format='{{.State.Status}}' \
			$$(docker compose -f airflow/docker-compose.yaml ps -q $$service) 2>/dev/null || echo "not_found"); \
		health=$$(docker inspect --format='{{.State.Health.Status}}' \
			$$(docker compose -f airflow/docker-compose.yaml ps -q $$service) 2>/dev/null || echo "none"); \
		echo "➡️  Service: $$service | Status: $$status | Health: $$health"; \
		if [ "$$status" != "running" ] || [ "$$health" = "unhealthy" ]; then \
			echo "⚠️  Service $$service is not healthy — showing last 20 logs..."; \
			docker compose -f airflow/docker-compose.yaml logs --tail=20 $$service || true; \
		fi; \
	done
	@if ! docker compose -f airflow/docker-compose.yaml exec webserver airflow db check >/dev/null 2>&1; then \
		echo "⚙️ Airflow DB not initialized — running airflow-init..."; \
		docker compose -f airflow/docker-compose.yaml run --rm airflow-init; \
	else \
		echo "✅ Airflow DB is already initialized."; \
	fi
	@echo "🔹 STEP 5: Verifying Airflow Webserver health..."
	@for i in $$(seq 1 30); do \
		if curl --silent http://localhost:8080/health | grep -q '"status":"healthy"'; then \
			echo "✅ Airflow Webserver is healthy!"; break; \
		fi; \
		echo "   Waiting... ($$i/30)"; sleep 5; \
	done
	@echo "🔹 STEP 6: Verifying MLflow health..."
	@if curl --silent http://localhost:5000 >/dev/null; then \
		echo "✅ MLflow UI is reachable!"; \
	else \
		echo "❌ MLflow UI not responding at http://localhost:5000"; \
	fi
	@echo "🔹 STEP 7: Verifying Serve API health..."
	@if curl --silent -X POST http://localhost:5001/invocations \
		-H "Content-Type: application/json" \
		-d '{"dataframe_split": {"columns": [], "data": []}}' | grep -q 'error_code'; then \
		echo "✅ Serve API is responding!"; \
	else \
		echo "❌ Serve API not responding at http://localhost:5001/invocations"; \
	fi
	@echo "🔹 STEP 8: Listing critical Airflow Variables..."
	@for var in MODEL_ALIAS PREDICTION_INPUT_PATH PREDICTION_OUTPUT_PATH STORAGE_BACKEND GCS_BUCKET LATEST_PREDICTION_PATH \
		MODEL_NAME PROMOTE_FROM_ALIAS PROMOTE_TO_ALIAS PROMOTION_AUC_THRESHOLD PROMOTION_F1_THRESHOLD \
		PROMOTION_TRIGGER_SOURCE PROMOTION_TRIGGERED_BY SLACK_WEBHOOK_URL ALERT_EMAILS; do \
		value=$$(docker compose -f airflow/docker-compose.yaml exec webserver airflow variables get $$var 2>/dev/null || echo "(not set)"); \
		echo "   • $$var = $$value"; \
	done
	@docker compose -f airflow/docker-compose.yaml ps

# === Terraform (GCP Infrastructure) ===
terraform-init:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform init"

terraform-plan:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform plan"

terraform-apply:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform apply -auto-approve"

terraform-destroy:
	docker compose -f airflow/docker-compose.yaml run --rm terraform "terraform destroy -auto-approve"

# === Integration Tests ===
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

# === Permissions & Logs ===
reset-logs:
	# Force-remove old logs even if owned by root/50000
	sudo rm -rf airflow/logs/*
	mkdir -p airflow/logs airflow/logs/dag_processor_manager
	sudo chown -R $(USER):$(USER) airflow/logs
	chmod -R 777 airflow/logs
	@echo "✅ Airflow logs reset with correct ownership."

fix-perms: reset-logs
	mkdir -p artifacts airflow/artifacts airflow/tmp mlruns
	sudo chmod -R 777 artifacts airflow/artifacts airflow/tmp mlruns
	# 👇 ensure Optuna DB path is writable
	sudo touch airflow/artifacts/optuna_study.db || true
	sudo chmod 666 airflow/artifacts/optuna_study.db || true
	chmod +x airflow/create_airflow_user.sh || true

# === One-shot setup for fresh envs (optional) ===
bootstrap:
	[ -f .env ] || cp -n .env.example .env || true
	$(MAKE) install
	$(MAKE) fix-perms
	$(MAKE) start

# === Emergency disk cleanup (Codespaces / Docker) ===
clean-disk:
	docker system prune -a -f --volumes
	sudo rm -rf airflow/logs/* mlruns/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	df -h /

# === Light, routine cleanup (safe) ===
clean-light:
	docker container prune -f
	docker image prune -f
	sudo rm -rf airflow/logs/* || true
	find . -type d -name "__pycache__" -exec rm -rf {} +
	df -h /

# === Backup & Restore Airflow Variables/Connections ===
backup-airflow:
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables export /opt/airflow/variables.json || true
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow connections export /opt/airflow/connections.json || true
	docker cp airflow-webserver:/opt/airflow/variables.json ./airflow/variables.json || true
	docker cp airflow-webserver:/opt/airflow/connections.json ./airflow/connections.json || true
	@echo "✅ Airflow Variables and Connections backed up to ./airflow/"

restore-airflow:
	docker cp ./airflow/variables.json airflow-webserver:/opt/airflow/variables.json || true
	docker cp ./airflow/connections.json airflow-webserver:/opt/airflow/connections.json || true
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables import /opt/airflow/variables.json || true
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow connections import /opt/airflow/connections.json || true
	@echo "✅ Airflow Variables and Connections restored"

reset: fix-perms export-env-vars
	docker compose -f airflow/docker-compose.yaml down -v
	docker compose -f airflow/docker-compose.yaml build
	docker compose -f airflow/docker-compose.yaml run --rm airflow-init
	docker compose -f airflow/docker-compose.yaml up -d postgres mlflow scheduler webserver
	# ✅ Auto-import variables
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables import /opt/airflow/variables.json
	@echo "✅ Reset complete (cached). Airflow UI → http://localhost:8080 | MLflow UI → http://localhost:5000"

fresh-reset: fix-perms export-env-vars
	docker compose -f airflow/docker-compose.yaml down -v
	docker compose -f airflow/docker-compose.yaml build --no-cache
	docker compose -f airflow/docker-compose.yaml run --rm airflow-init
	docker compose -f airflow/docker-compose.yaml up -d postgres mlflow scheduler webserver
	# ✅ Auto-import variables
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables import /opt/airflow/variables.json
	@echo "✅ Fresh reset complete (no cache). Airflow UI → http://localhost:8080 | MLflow UI → http://localhost:5000"

restart-webserver:
	docker compose -f airflow/docker-compose.yaml restart webserver
	@echo "🔄 Webserver restarted. Check logs with: docker compose -f airflow/docker-compose.yaml logs -f webserver"

restart-serve:
	docker compose -f airflow/docker-compose.yaml restart serve
	@echo "🔄 Serving container restarted. Health check: curl -s http://localhost:5001/ping"

# === Reset Airflow Variables (for stop_all.sh --reset-vars) ===
reset-vars:
	@echo "🗑 Clearing Phase 2 & Phase 3 Airflow Variables..."
	@for var in MODEL_ALIAS PREDICTION_INPUT_PATH PREDICTION_OUTPUT_PATH STORAGE_BACKEND GCS_BUCKET LATEST_PREDICTION_PATH \
		MODEL_NAME PROMOTE_FROM_ALIAS PROMOTE_TO_ALIAS PROMOTION_AUC_THRESHOLD PROMOTION_F1_THRESHOLD \
		PROMOTION_TRIGGER_SOURCE PROMOTION_TRIGGERED_BY SLACK_WEBHOOK_URL ALERT_EMAILS; do \
		echo "   • Removing Airflow Variable: $$var"; \
		docker compose -f airflow/docker-compose.yaml run --rm webserver airflow variables delete $$var || true; \
	done
	@echo "✅ Airflow Variables cleared."

# === Verify Airflow & MLflow health ===
verify:
	@echo "🔎 Checking Airflow version..."
	-@docker exec -it airflow-webserver airflow version || echo "❌ Airflow not responding"

	@echo "\n📂 Listing DAGs inside Airflow container..."
	-@docker exec -it airflow-webserver ls -l /opt/airflow/dags || echo "❌ DAGs not mounted"

	@echo "\n🌐 Checking Airflow webserver health..."
	-@curl -s http://localhost:8080/health || echo "❌ Airflow UI not reachable"

	@echo "\n📡 Checking MLflow logs (last 20 lines)..."
	-@docker compose -f airflow/docker-compose.yaml logs --tail=20 mlflow || echo "❌ MLflow not starting"

	@echo "\n✅ Verification complete"

# === Vertex AI Trainer Image ===
PROJECT_ID ?= loan-default-mlops
REGION ?= us-central1
REPO ?= mlops
IMAGE ?= loan-default-trainer
TAG ?= latest
TRAINER_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:${TAG}

gcloud-auth:
	@echo "🔐 Ensuring Docker is authenticated with Artifact Registry..."
	-gcloud auth configure-docker ${REGION}-docker.pkg.dev

build-trainer: gcloud-auth
	docker build -f Dockerfile.trainer -t ${TRAINER_IMAGE} .

push-trainer: gcloud-auth
	docker push ${TRAINER_IMAGE}

trainer: build-trainer push-trainer

set-trainer-image:
	docker compose -f airflow/docker-compose.yaml exec webserver \
		airflow variables set TRAINER_IMAGE_URI ${TRAINER_IMAGE}
	@echo "✅ Airflow variable TRAINER_IMAGE_URI set to ${TRAINER_IMAGE}"


# === Generate Airflow Variables from .env ===
export-env-vars:
	@echo "📦 Exporting .env → airflow/variables.json"
	@python3 scripts/export_env_vars.py
