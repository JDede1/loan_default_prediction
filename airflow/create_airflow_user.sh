#!/bin/bash
set -euo pipefail

# Load .env variables
if [ -f /opt/airflow/.env ]; then
    set -a
    source /opt/airflow/.env
    set +a
fi

USERNAME="${_AIRFLOW_WWW_USER_USERNAME:-admin}"
FIRSTNAME="${_AIRFLOW_WWW_USER_FIRSTNAME:-Air}"
LASTNAME="${_AIRFLOW_WWW_USER_LASTNAME:-Flow}"
ROLE="${_AIRFLOW_WWW_USER_ROLE:-Admin}"
EMAIL="${_AIRFLOW_WWW_USER_EMAIL:-admin@example.org}"
PASSWORD="${_AIRFLOW_WWW_USER_PASSWORD:-admin}"

echo "👤 Checking if Airflow user '$USERNAME' exists..."

if airflow users list | grep -q "$USERNAME"; then
    echo "ℹ️ User '$USERNAME' already exists — skipping creation."
else
    echo "👤 Creating Airflow admin user: $USERNAME"
    airflow users create \
      --username "$USERNAME" \
      --firstname "$FIRSTNAME" \
      --lastname "$LASTNAME" \
      --role "$ROLE" \
      --email "$EMAIL" \
      --password "$PASSWORD"
    echo "✅ Airflow admin user created (username: $USERNAME / password: $PASSWORD)"
fi
