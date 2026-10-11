# Urban Environmental Intelligence & Prediction Platform (Urban EIPP)

An enterprise-grade, cloud-native environmental intelligence and predictive analytics platform engineered for real-time air quality monitoring, atmospheric anomaly detection, and 24-hour pollutant forecasting.

---

## 1. System Architecture

```
                       +-----------------------------------+
                       |    Google Colab Model Training    |
                       | (LightGBM, Chronological Splits)  |
                       +-----------------+-----------------+
                                         |
                                   Uploads Models
                                         |
                                         v
+-----------------------+     +--------------------+     +-----------------------+
|  OpenAQ / Open-Meteo  | --> | S3 Model Registry  | <-- |   Analytics Service   |
+-----------+-----------+     |  (Persistent Tier) |     | (Inference Only: 5001)|
            |                 +--------------------+     +-----------+-----------+
      Ingests Telemetry                                              |
            |                                                        v
+-----------v-----------+     +--------------------+     +-----------------------+
|    Data Collector     | --> |   Data Processor   | --> |      API Gateway      |
|     (Port: 8080)      |     |    (Port: 5000)    |     |  (Express.js: 3000)   |
+-----------------------+     +----+----------+----+     +-----------+-----------+
                                   |          |                      |
                        Raw/Processed S3   PostgreSQL                v
                           Data Lake      TimescaleDB    +-----------------------+
                                                         |  Web React Dashboard  |
                                                         |       (Port: 80)      |
                                                         +-----------------------+
```

### Microservices Summary
1. **`data-collector`** (Python/FastAPI): Scheduled poller (900s interval) checking freshness via `GET /latest`, collecting real-time air quality & weather for due cities, and dispatching atomic batches.
2. **`data-processor`** (Python/FastAPI): Normalizes observations, archives immutable raw JSON & processed Parquet to S3, and executes idempotent `COALESCE` upserts into PostgreSQL.
3. **`analytics-service`** (Python/FastAPI): Production inference engine with lazy S3 model loading, in-memory positive/negative caching, and advisory-lock scheduled predictions. (Strictly inference-only: `/train` returns 403 Forbidden).
4. **`api-service`** (Node.js/Express): JWT-authenticated REST gateway serving city telemetry, forecasts, and alert management.
5. **`web-dashboard`** (React/Vite): Modern glassmorphic analytics dashboard rendering real-time KPI cards, interactive 48h actuals + 24h predictive horizon charts, and anomaly alerts.

---

## 2. Key Architectural Decisions

- **ML Training Outside Cluster**: Machine learning models are trained in Google Colab (LightGBM with chronological train/validation/test splits against persistence baselines) and synced directly to S3. Production pods do not train in-pod, preventing OOM crashes.
- **Docker Images from Docker Hub**: Container images are built in CI/CD and pulled directly by Kubernetes / Docker Compose.
- **Two-Tier Terraform Architecture**:
  - `terraform/persistent/`: S3 buckets (`raw`, `processed`, `models`) with `prevent_destroy = true`. Never touched during compute maintenance.
  - `terraform/compute/`: Single-click disposable compute tier (EC2, k3s, Ingress-Nginx, PostgreSQL, microservices). Cleanly destroyed with `terraform destroy` without losing any ML models or historical data.

---

## 3. Local Development (Docker Compose)

### Prerequisites
- Docker Engine & Docker Compose
- Python 3.12+ (or virtual environment: `source ~/myEnv/bin/activate`)
- Node.js 22 LTS

### Starting the Platform
```bash
# 1. Copy local configuration
cp .env.example .env

# 2. Build and launch all services
docker compose up --build -d

# 3. Check service health
docker compose ps
```

### Accessing Endpoints
- **Web Dashboard**: [http://localhost:80](http://localhost:80)
- **API Health Check**: `curl http://localhost:3000/api/health`
- **Data Processor Freshness**: `curl http://localhost:5000/latest`
- **Data Collector Telemetry**: `curl http://localhost:8080/health`
- **Analytics Health**: `curl http://localhost:5001/health`
- **MinIO Object Console**: [http://localhost:9001](http://localhost:9001) (`minioadmin` / `minioadmin`)

---

## 4. Single-Click AWS Cloud Deployment

```bash
# 1. Deploy Persistent S3 Data Lake & Model Registry (Run once)
cd terraform/persistent
terraform init && terraform apply

# 2. Deploy Disposable Compute Stack (Single-Click)
cd ../compute
cp terraform.tfvars.example terraform.tfvars # set admin_cidrs and bucket names
terraform init && terraform apply

# Follow bootstrap logs via SSH
$(terraform output -raw ssh_command)
tail -f /var/log/user-data.log
```

---

## 5. Teardown
```bash
# Cleanly destroy compute while preserving all models and data:
cd terraform/compute
terraform destroy
```
