# 🌍 Urban Environmental Intelligence & Prediction Platform (UrbanEIIP)

[![Build Status](https://img.shields.io/badge/CI%2FCD-Jenkins%20Automated-blue?logo=jenkins)](http://184.196.112.96:8080)
[![AWS Cloud](https://img.shields.io/badge/AWS-EC2%20%7C%20S3%20%7C%20EIP-orange?logo=amazon-aws)](https://aws.amazon.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-K3s%20Cluster-326ce5?logo=kubernetes)](https://k3s.io)
[![Machine Learning](https://img.shields.io/badge/ML-LightGBM%20Delta%20Residual-brightgreen?logo=scikit-learn)](https://lightgbm.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚀 Live Public Deployment

The complete cloud-native infrastructure is actively provisioned and hosted on AWS with a dedicated Elastic IP:

| Component | Endpoint | Description |
| :--- | :--- | :--- |
| **🌐 Interactive Dashboard** | [http://app.184.196.112.96.nip.io](http://app.184.196.112.96.nip.io) | React Frontend with Multi-Metric Forecasting & On-Demand Telemetry Refresh |
| **🔌 API Gateway** | [http://api.184.196.112.96.nip.io](http://api.184.196.112.96.nip.io) | Node.js Express Gateway (Auth, Telemetry, Health, Inference Trigger) |
| **🩺 API Health Check** | [http://api.184.196.112.96.nip.io/health](http://api.184.196.112.96.nip.io/health) | Real-time service readiness & database connectivity verification |
| **⚙️ Jenkins CI/CD Console** | [http://184.196.112.96:8080](http://184.196.112.96:8080) | Continuous Integration & Automated Delivery Pipeline Controller |
| **🪝 GitHub Webhook URL** | `http://184.196.112.96:8080/github-webhook/` | Target URL configured in GitHub Repository Settings for automated build triggers |
| **📍 Dedicated Elastic IP** | `184.196.112.96` | Static AWS IPv4 Allocation (`us-east-1`) |

---

## 📖 Executive Summary

**Urban Environmental Intelligence & Prediction Platform (UrbanEIIP)** is a production-grade, distributed IoT and environmental telemetry platform designed for continuous air quality monitoring, automated anomaly detection, and forward-looking meteorological forecasting.

### Key Capabilities
- **Real-Time Telemetry Ingestion**: Asynchronous multi-threaded ingestion from Central Pollution Control Board (CPCB), OpenAQ, and Open-Meteo across key Indian metropolitan areas.
- **Delta-Residual Machine Learning**: Chronologically trained **LightGBM** models for PM2.5 and PM10 that predict delta movements against rolling baselines, eliminating static disparity.
- **Regional Meteorological Fallback**: Dynamic regional matrix ensuring high-availability ML inference (e.g. Pune/Ahmedabad $\to$ Mumbai, Lucknow/Jaipur $\to$ Delhi).
- **Interactive Multi-Metric Toggle**: Instant switching between `[ PM2.5 ]`, `[ PM10 ]`, and `[ Composite AQI ]` with official CPCB breakpoint interpolation.
- **On-Demand Force Refresh**: User-triggered live collection, S3 synchronization, and re-inference directly from the dashboard.
- **Ultra-Lean Resource Footprint**: Entire 5-service cluster runs inside ~650 MiB RAM on a single cost-optimized K3s node with 2 GB swap guard.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
  subgraph DataSources["External Environmental Telemetry"]
    CPCB["CPCB / OpenAQ v3 API"]
    METEO["Open-Meteo Historical & Forecast"]
  end

  subgraph IngestionAndProcessing["Ingestion & Data Pipeline"]
    DC["data-collector<br/>(FastAPI / Python 3.12)"]
    DP["data-processor<br/>(Python 3.12 / Pandas)"]
    DB[("PostgreSQL 16<br/>Timescale Telemetry DB")]
    S3_RAW[("AWS S3 Raw Archive")]
    S3_PROC[("AWS S3 Processed Parquet")]
  end

  subgraph AnalyticsAndML["Machine Learning & Analytics"]
    ANA["analytics-service<br/>(LightGBM / Scikit-Learn)"]
    S3_MODELS[("AWS S3 Model Registry")]
  end

  subgraph PresentationGateway["Gateway & Presentation"]
    API["api-service<br/>(Node.js 22 / Express)"]
    UI["web-dashboard<br/>(React 18 / Vite / Tailwind)"]
  end

  CPCB -->|Polls Telemetry| DC
  METEO -->|Fetches Meteorology| DC
  DC -->|Raw Payloads| DP
  DC -->|Raw JSON Objects| S3_RAW
  DP -->|Validated Hourly Aggregates| DB
  DP -->|Daily Snappy Parquet| S3_PROC
  ANA -->|Delta Residual Inference| DB
  S3_MODELS -->|Pre-trained Weights| ANA
  DB -->|Queries State| API
  ANA -->|Forecast Vectors| API
  API -->|REST / JSON| UI
```

---

## 📂 Repository Structure

```text
Urban-Environmental-Intelligence-Prediction-Platform/
├── Jenkinsfile                  # Declarative Jenkins CI/CD pipeline (SCM Webhook driven)
├── README.md                    # Platform documentation, live URLs & architecture guide
├── docker-compose.yml           # Single-command local developer environment
├── .env.example                 # Standardized environment template
├── .gitignore                   # Production gitignore rules (excludes secrets & extras)
│
├── services/                    # Microservices Source Code
│   ├── data-collector/          # Periodic & On-Demand Telemetry Ingestion (Python/FastAPI)
│   ├── data-processor/          # Telemetry cleaning, outlier filtering & hourly rollups
│   ├── analytics-service/       # LightGBM inference, regional fallback & AQI scoring
│   ├── api-service/             # Express.js REST gateway, JWT authentication & proxy
│   └── web-dashboard/           # Modern React SPA with interactive charts & metric toggles
│
├── terraform/                   # Infrastructure as Code (AWS)
│   ├── persistent/              # S3 Data Buckets (raw, processed, model registry)
│   └── compute/                 # EC2 (Ubuntu 22.04 LTS), Dedicated Elastic IP, Security Groups, K3s
│
├── helm/                        # Kubernetes Helm Charts
│   └── urban-platform/          # Parameterized microservices deployment & Ingress rules
│
├── k8s/                         # Raw Kubernetes Manifests (Fallback / Reference)
│
├── notebooks/                   # ML Training & Research Notebooks
│   └── urban_training.ipynb     # 180-day bootstrap, cross-validation & model gating
│
├── scripts/                     # Platform Automation
│   └── push_docker_images.sh    # Automated Docker Hub tagging and publishing
│
└── extras/                      # [GIT-IGNORED] Local Development & Test Artifacts
    ├── README.md                # Guide to offline test harnesses
    ├── scripts/                 # Reusable offline test scripts (e.g., seed_all_cities.py)
    ├── testing/                 # API mocks and unit testing harnesses
    └── scratch/                 # Intermediate test data & scratchpads
```

> **Note on `extras/`:** All local testing files, city seeders, and experimental test code are preserved inside `extras/`. This directory is strictly ignored by Git so that local testing can be repeated without cluttering the repository.

---

## 🛠️ Build & Run Your Own UrbanEIIP Stack

You can reproduce this entire architecture either locally using Docker Compose or on AWS using the provided Terraform configurations.

### Option A: Local Deployment (Docker Compose)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Akash123-cyber/Urban-Environmental-Intelligence-Prediction-Platform.git
   cd Urban-Environmental-Intelligence-Prediction-Platform
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env if you wish to adjust poll intervals or add an OpenAQ API key
   ```

3. **Launch Microservices:**
   ```bash
   docker compose up -d
   ```

4. **Access Local Endpoints:**
   - **Web Dashboard:** [http://localhost:8080](http://localhost:8080)
   - **API Gateway:** [http://localhost:3000](http://localhost:3000)
   - **API Health:** [http://localhost:3000/health](http://localhost:3000/health)

---

### Option B: Cloud Deployment on AWS (Terraform + K3s)

#### 1. Prerequisites
- [AWS CLI v2](https://aws.amazon.com/cli/) configured with valid administrator credentials.
- [Terraform >= 1.5](https://www.terraform.io/downloads.html).
- An existing or imported EC2 Key Pair (`~/.ssh/id_rsa.pub` or similar).

#### 2. Provision Persistent Storage (S3 Buckets)
```bash
cd terraform/persistent
terraform init
terraform apply -auto-approve
```
*Outputs: `raw`, `processed`, and `models` S3 bucket names.*

#### 3. Upload Trained Model Artifacts
Upload the included LightGBM model weights to the newly created S3 model registry bucket:
```bash
# From repository root:
aws s3 sync data/models/ s3://<models-bucket-name>/
```

#### 4. Provision Compute Layer & Dedicated Elastic IP
```bash
cd ../compute
cp terraform.tfvars.example terraform.tfvars
```
Update `terraform.tfvars`:
```hcl
region          = "us-east-1"
key_name        = "your-ec2-key-name"
admin_cidrs     = ["<your-ip-address>/32"]
bucket_names    = {
  raw       = "your-raw-bucket-name"
  processed = "your-processed-bucket-name"
  models    = "your-models-bucket-name"
}
docker_registry = "docker.io/akash123cyber"
docker_tag      = "latest"
```

Apply compute infrastructure:
```bash
terraform init
terraform apply -auto-approve
```

Terraform automatically provisions:
1. **Ubuntu 22.04 LTS EC2 Instance** with 2 GB Swap protection.
2. **Dedicated AWS Elastic IP** attached permanently to the node.
3. **AWS Security Group** with inbound access for HTTP (80), HTTPS (443), and Jenkins (8080).
4. **K3s Single-Node Kubernetes Cluster** with Ingress-Nginx controller.
5. **Jenkins CI/CD Server** running directly on port 8080.

---

## 🔄 Automated CI/CD with Jenkins & GitHub Webhooks

The platform features automated SCM-triggered CI/CD:

```mermaid
sequenceDiagram
  autonumber
  actor Developer
  participant GitHub
  participant Jenkins as Jenkins CI (:8080)
  participant DockerHub as Docker Hub Registry
  participant K3s as AWS K3s Cluster

  Developer->>GitHub: git push origin main
  GitHub->>Jenkins: POST /github-webhook/
  Jenkins->>Jenkins: Parallel Pytest, Jest, Lint & Build
  Jenkins->>DockerHub: Build & Push SHA-tagged Docker Images
  Jenkins->>K3s: Rolling update deployments via kubectl / Helm
  Jenkins->>K3s: Smoke test GET /api/health
```

### Setting Up the GitHub Webhook
1. Go to your GitHub Repository $\to$ **Settings** $\to$ **Webhooks** $\to$ **Add webhook**.
2. **Payload URL**: `http://184.196.112.96:8080/github-webhook/`
3. **Content type**: `application/json`
4. **Events**: Select **Just the push event**.
5. Save the webhook. Every subsequent `git push` to `main` will automatically trigger parallel validation, container compilation, and rolling cluster deployment!

---

## 🧪 Local Testing & Seeding Harnesses

To seed telemetry or test without calling live CPCB endpoints repeatedly, use the scripts preserved in `extras/`:

```bash
# Seed telemetry across all target cities using historical Open-Meteo & OpenAQ data:
python extras/scripts/seed_all_cities.py
```

---

## 📜 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
