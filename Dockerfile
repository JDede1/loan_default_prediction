# Dockerfile for Airflow services (webserver, scheduler, init)
FROM python:3.8-slim

# Set environment variables
ENV AIRFLOW_HOME=/opt/airflow
ENV PATH=$AIRFLOW_HOME/.local/bin:$PATH

# Install system-level dependencies, including bash explicitly
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    default-libmysqlclient-dev \
    libpq-dev \
    git \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Apache Airflow with pinned constraints for Python 3.8
RUN pip install apache-airflow==2.8.1 \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.8.1/constraints-3.8.txt"

# Install PostgreSQL adapter
RUN pip install psycopg2-binary

# Copy requirements first to leverage Docker build cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly install Evidently if not in requirements.txt
RUN pip install evidently

# Create airflow user to match docker-compose UID (avoids permission issues)
RUN useradd -ms /bin/bash airflow && \
    mkdir -p ${AIRFLOW_HOME}/logs && \
    chown -R airflow:airflow ${AIRFLOW_HOME}

# Set working directory
WORKDIR ${AIRFLOW_HOME}

# Expose Airflow Webserver port
EXPOSE 8080

# Run as airflow user by default
USER airflow

# Default command (overridden by docker-compose)
CMD ["airflow", "webserver"]
