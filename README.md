<h1 align=center>ML System: Docker + Kubernetes — End-to-End Project</h1>

# Phase 1

- We'll train a simple but realistic Iris flower classifier (multi-class) using scikit-learn. The goal is clean, production-ready code with proper artifact saving.

### Phases

| Phase | Description                        | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Train & Save ML Model              | ✅     |
| 2     | Containerize with Docker + FastAPI | 🔜     |
| 3     | Local Docker Testing               | 🔜     |
| 4     | Kubernetes Manifests               | 🔜     |
| 5     | Deploy & Scale on Kubernetes       | 🔜     |
| 6     | Monitoring & Observability         | 🔜     |

## 🛠️ Installation & Setup

#### Prerequisites

- Python 3.10+
- pip
- Git

1. Create new git repo and clone the Repository

```bash
git clone https://github.com/FraidoonOmarzai/---
cd ---
```

2. Create Virtual Environment

```bash
# Create virtual environment
conda create -n dock8s python=3.12 -y

# Activate virtual environment
conda activate dock8s
```

3. Install Dependencies

```bash
pip install -r requirements.txt
```

4. Create Directory Structure (Define template of the project)

```bash
touch template.py #linux/Mac
python3 template.py
```

5. Define Logger and Custom Exception

## Phase 1 — Run Training

#### Project Structure for Phase 1

```
ml-k8s-project/
├── model/
│   ├── train.py
│   ├── evaluate.py
│   └── artifacts/          ← saved model + scaler land here
├── requirements-train.txt
└── README.md
```

```bash
# Train the model (saves artifacts to model/artifacts/)
python model/train.py

# evaluation
python model/evaluate.py
```

Expected output:

```
✅ Training complete!
   Model    → model/artifacts/model.pkl
   Metadata → model/artifacts/metadata.json
   Test Accuracy: 0.933
```

#### ✅ Phase 1 Complete — Here's what was built:

model/train.py does the following in clean, production-style code:

- Loads the Iris dataset
- Builds a Pipeline (StandardScaler → RandomForestClassifier) — the scaler is bundled inside the pipeline so you never have a mismatch at inference time
- Runs 5-fold cross validation and logs scores
- Saves model.pkl (the full pipeline) and metadata.json (feature names, class names, accuracy, etc.)

model/evaluate.py loads the saved artifacts and runs 3 sample predictions to confirm the model is healthy before containerizing.

---

---

---

# Phase 2 — What To Do (Step by Step)

- We'll build a production-ready REST API around the model, then Dockerize it properly.

### Phases

| Phase | Description                        | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Train & Save ML Model              | ✅     |
| 2     | Containerize with Docker + FastAPI | ✅     |
| 3     | Local Docker Testing               | 🔜     |
| 4     | Kubernetes Manifests               | 🔜     |
| 5     | Deploy & Scale on Kubernetes       | 🔜     |
| 6     | Monitoring & Observability         | 🔜     |

#### Project Structure after Phase 2

```
ml-k8s-project/
├── model/
│   ├── train.py
│   ├── evaluate.py
│   └── artifacts/
│       ├── model.pkl
│       └── metadata.json
├── app/                        ← NEW
│   ├── main.py                 ← FastAPI app
│   ├── predictor.py            ← model loading + inference logic
│   └── schemas.py              ← Pydantic request/response models
├── Dockerfile                  ← NEW
├── .dockerignore               ← NEW
├── requirements-train.txt
├── requirements-serve.txt      ← NEW
└── README.md
```

### What Phase 2 is about

You're wrapping the trained model in a FastAPI web server and packaging it into a Docker container. Here's the full sequence:

#### Step 1 — Make sure Phase 1 artifacts exist

```bash
# You should already have these from Phase 1:
ls model/artifacts/
# model.pkl
# metadata.json

# If not, run training first:
pip install -r requirements-train.txt
python model/train.py
```

#### Step 2 — Install serving dependencies

```bash
pip install -r requirements-serve.txt
```

#### Step 3 — Test the FastAPI server locally (before Docker)

```bash
# Run from the project root
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

# You should see:
# INFO | Loading model...
# INFO | Model ready. Server accepting requests.
# INFO | Uvicorn running on http://0.0.0.0:8080
```

#### Step 4 — Verify the API works

```bash
# Health check
curl http://localhost:8080/health

# Single prediction
curl -X POST http://localhost:8080/predict \
     -H "Content-Type: application/json" \
     -d '{"features": [5.1, 3.5, 1.4, 0.2]}'

# Expected response:
# {
#   "predicted_class": "setosa",
#   "predicted_index": 0,
#   "probabilities": {"setosa": 0.97, ...},
#   "model_version": "RandomForestClassifier_v1"
# }

# Also open Swagger UI in browser:
# http://localhost:8080/docs
```

#### Step 5 — Build the Docker image

```bash
# Stop the uvicorn server first (Ctrl+C), then:
docker build -t fraidoonjan/dock8s:latest .

# Verify image was created
docker image ls fraidoonjan/dock8s
```

#### Step 6 — Run the container

```bash
docker run -d \
  --name dock8s-api \
  -p 8080:8080 \
  fraidoonjan/dock8s:latest

# Check it started cleanly
docker logs dock8s-api
```

#### Step 7 — Verify the container works

```bash
curl http://localhost:8080/health
# Should return {"status": "healthy", ...}
```

#### ✅ Phase 2 Complete — Here's what was built:

- `app/schemas.py` — Pydantic v2 models with validation for single + batch requests, clean error messages on bad input.
- `app/predictor.py` — Singleton `ModelPredictor` class that loads the pipeline once at startup and serves both single and batch inference. Path is configurable via `ARTIFACTS_DIR` env var (important for Kubernetes).

- `app/main.py` — FastAPI app with:
  - `/health` — liveness probe (returns model metadata)
  - `/ready` — readiness probe (returns 200 only when model is loaded)
  - `/predict` — single inference
  - `/predict/batch` — batch inference (up to 100 samples)
  - Request timing middleware logging every request's latency

- Dockerfile — Multi-stage build:
  - Stage 1 (builder): installs all deps into a venv
  - Stage 2 (runtime): copies only the venv + app code, no compilers, runs as a non-root user — production best practice

---

---

---

# Phases 3 — Local Docker Testing

- We'll build the image, run the container, and thoroughly test every endpoint. This phase is all about commands you run in your terminal — plus a test script to automate it all.

### Phases

| Phase | Description                        | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Train & Save ML Model              | ✅     |
| 2     | Containerize with Docker + FastAPI | ✅     |
| 3     | Local Docker Testing               | ✅     |
| 4     | Kubernetes Manifests               | 🔜     |
| 5     | Deploy & Scale on Kubernetes       | 🔜     |
| 6     | Monitoring & Observability         | 🔜     |

#### Option A — One-shot script (recommended)

```bash
## run it using git bash terminal if using windows inside VS
chmod +x run_local.sh && ./run_local.sh ###=>an error
```

#### Option B — Manual

```bash
python test_local.py
python test_local.py --base-url http://localhost:9090
```

```bash
### From phase 1 Step-by-Step Manual
# 1. Train and save artifacts
pip install -r requirements-train.txt
python model/train.py

# 2. Build the image
docker build -t fraidoonjan/dock8s:latest .

# 3. Run the container
docker run -d --name dock8s-api -p 8080:8080 fraidoonjan/dock8s:latest

# 4. Test it manually with curl
curl http://localhost:8080/health
curl -X POST http://localhost:8080/predict \
     -H "Content-Type: application/json" \
     -d '{"features": [5.1, 3.5, 1.4, 0.2]}'

# 5. Run the full test suite
python test_local.py

# 6. Check logs
docker logs -f dock8s-api
```

#### Option C — Docker Compose

```bash
docker compose up --build
docker compose --profile test up
```

- Useful Docker commands

```bash
docker logs -f dock8s-api
docker exec -it dock8s-api bash
docker stats dock8s-api
docker stop dock8s-api && docker rm dock8s-api
```

---

---

---

# Phase 4

We'll write every K8s resource needed for a production-grade deployment. Here's the full structure we're building:

```
ml-k8s-project/
└── k8s/
    ├── namespace.yaml          ← isolated environment
    ├── configmap.yaml          ← app config & env vars
    ├── deployment.yaml         ← pods, replicas, probes, resources
    ├── service.yaml            ← internal + external networking
    └── ingress.yaml            ← optional HTTP routing
```

# Running Phase 4 Manually — Step by Step

Everything the script does, broken down into individual kubectl commands you run one at a time.

Prerequisites

```bash
# Make sure you have a running cluster
minikube start --cpus=4 --memory=4g
```

### Step 1 — Train the model and build the Docker image

- `note:` we runned everything in previous steps!

```bash
# Train and save artifacts
pip install -r requirements-train.txt
python model/train.py

# Build the image
docker build -t your-dockerhub-username/dock8s:latest .
# Push docker image to docker hub
docker push your-dockerhub-username/dock8s:latest
```

### Step 2 — Apply the Namespace

```bash
kubectl apply -f k8s/namespace.yaml

# Verify
kubectl get namespace dock8s-namespace
```

`Expected output:`

```
NAME        STATUS   AGE
dock8s-namespace   Active   5s
```

### Step 3 — Apply the ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml

# Verify
kubectl get configmap -n dock8s-namespace
kubectl describe configmap dock8s-api-config -n dock8s-namespace
```

Step 4 — Apply the Deployment

```bash
kubectl apply -f k8s/deployment.yaml

# Watch pods come up in real time
kubectl get pods -n dock8s-namespace -w
```

You'll see pods go through: Pending → ContainerCreating → Running. Wait until the READY column shows 1/1 for both pods. Then press Ctrl+C to stop watching.

```bash
# Confirm both replicas are ready
kubectl get deployment dock8s-api -n dock8s-namespace
```

`Expected:`

```
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
dock8s-api    2/2     2            2           30s
```

If pods aren't becoming ready, check what's wrong:

```bash
# See events and probe results
kubectl describe pod -l app=dock8s-api -n dock8s-namespace

# See container logs
kubectl logs -l app=dock8s-api -n dock8s-namespace
```

### Step 5 — Apply the Service

```bash
kubectl apply -f k8s/service.yaml

# Verify both services were created
kubectl get svc -n dock8s-namespace
```

`Expected:`

```
NAME                    TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
api-service          LoadBalancer   10.102.17.147   <pending>     80:30309/TCP   40d
dock8s-api-service   LoadBalancer   10.101.44.63    <pending>     80:32670/TCP   31d
```

The EXTERNAL-IP will stay <pending> until you run minikube tunnel (see access step below).

### Step 6 — Apply the Ingress

```bash
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get ingress -n dock8s-namespace
```

### Step 7 — Access the API

- Port-forward (easiest, works always):

```bash
kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace
```

- In a second terminal:
  curl http://localhost:8080/health

### Step 8 — Verify everything is healthy

```bash
# All resources at a glance
kubectl get all -n dock8s-namespace

# Detailed deployment status
kubectl rollout status deployment/dock8s-api -n dock8s-namespace

# Pod resource usage (requires metrics-server)
kubectl top pods -n dock8s-namespace
```
