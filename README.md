<h1 align=center>ML System: Docker + Kubernetes — End-to-End Project</h1>

## Phases
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Train & Save ML Model | ✅ |
| 2 | Containerize with Docker + FastAPI | 🔜 |
| 3 | Local Docker Testing | 🔜 |
| 4 | Kubernetes Manifests | 🔜 |
| 5 | Deploy & Scale on Kubernetes | 🔜 |
| 6 | Monitoring & Observability | 🔜 |

## Phase 1 — Run Training

```bash
# Install dependencies
pip install -r requirements-train.txt

# Train the model (saves artifacts to model/artifacts/)
python model/train.py

# Sanity check
python model/evaluate.py
```

Expected output:
```
✅ Training complete!
   Model    → model/artifacts/model.pkl
   Metadata → model/artifacts/metadata.json
   Test Accuracy: 0.9667
```

## Phase 2 — What To Do (Step by Step)
## Phases
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Train & Save ML Model | ✅ |
| 2 | Containerize with Docker + FastAPI | ✅ |
| 3 | Local Docker Testing | 🔜 |
| 4 | Kubernetes Manifests | 🔜 |
| 5 | Deploy & Scale on Kubernetes | 🔜 |
| 6 | Monitoring & Observability | 🔜 |

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
docker build -t iris-ml-api:latest .

# Verify image was created
docker image ls iris-ml-api
```
#### Step 6 — Run the container
```bash
docker run -d \
  --name iris-ml-local \
  -p 8080:8080 \
  iris-ml-api:latest

# Check it started cleanly
docker logs iris-ml-local
```
#### Step 7 — Verify the container works
```bash
curl http://localhost:8080/health
# Should return {"status": "healthy", ...}
```

#### Common errors and fixes
- ModuleNotFoundError: No module named 'app' — run uvicorn from the project root, not from inside the app/ folder.
- FileNotFoundError: model.pkl not found — artifacts weren't generated. Run python model/train.py first.
- Port already in use — something else is on 8080. Use -p 9090:8080 to map to a different local port.
- Docker build fails on scikit-learn — make sure Docker Desktop is running and has enough memory (at least 2GB).

## Phases
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Train & Save ML Model | ✅ |
| 2 | Containerize with Docker + FastAPI | ✅ |
| 3 | Local Docker Testing | ✅ |
| 4 | Kubernetes Manifests | 🔜 |
| 5 | Deploy & Scale on Kubernetes | 🔜 |
| 6 | Monitoring & Observability | 🔜 |

```
Phase 1 — Train the Model
bashpip install -r requirements-train.txt
python model/train.py
python model/evaluate.py
Expected output:
✅ Training complete!
   Model     → model/artifacts/model.pkl
   Metadata  → model/artifacts/metadata.json
   Test Accuracy: 0.9667

Phase 2 — FastAPI Server + Docker
Run locally (without Docker)
bashpip install -r requirements-serve.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
Open http://localhost:8080/docs for the Swagger UI.
Build and run with Docker
bashdocker build -t iris-ml-api:latest .
docker run -d --name iris-ml-local -p 8080:8080 iris-ml-api:latest
docker logs iris-ml-local
API Endpoints
MethodPathDescriptionGET/healthLiveness probe — returns model infoGET/readyReadiness probe — 200 when readyPOST/predictSingle prediction (4 features)POST/predict/batchBatch predictions (up to 100)GET/docsSwagger UI
Example requests
bashcurl http://localhost:8080/health

curl -X POST http://localhost:8080/predict \
     -H "Content-Type: application/json" \
     -d '{"features": [5.1, 3.5, 1.4, 0.2]}'

curl -X POST http://localhost:8080/predict/batch \
     -H "Content-Type: application/json" \
     -d '{"features": [[5.1,3.5,1.4,0.2],[6.7,3.0,5.2,2.3]]}'
Common errors
ErrorFixModuleNotFoundError: No module named 'app'Run uvicorn from project rootFileNotFoundError: model.pkl not foundRun python model/train.py firstPort already in useUse -p 9090:8080 to remap the portDocker build failsEnsure Docker Desktop has at least 2GB RAM
```
## Phase 3 — Local Docker Testing
- One-shot script (recommended)
```bash
chmod +x run_local.sh && ./run_local.sh
```
- Manual
```bash
python test_local.py
python test_local.py --base-url http://localhost:9090
```
- Docker Compose
```bash
docker compose up --build
docker compose --profile test up
```
- Useful Docker commands
```bash
docker logs -f iris-ml-local
docker exec -it iris-ml-local bash
docker stats iris-ml-local
docker stop iris-ml-local && docker rm iris-ml-local
```



### Running Phase 4 Manually — Step by Step
Everything the script does, broken down into individual kubectl commands you run one at a time.

Prerequisites
```bash
# Make sure you have a running cluster
minikube start --cpus=4 --memory=4g

# Enable ingress addon
minikube addons enable ingress

# Enable metrics-server (needed for HPA)
minikube addons enable metrics-server

# Verify kubectl is pointed at minikube
kubectl config current-context
# should output: minikube
```
Step 1 — Train the model and build the Docker image
```bash
# Train and save artifacts
pip install -r requirements-train.txt
python model/train.py

# Build the image
docker build -t iris-ml-api:latest .

# Load it into minikube's Docker daemon
# (minikube can't pull from your local Docker by default)
minikube image load iris-ml-api:latest

# Verify it's there
minikube image ls | grep iris
```
Step 2 — Apply the Namespace
```bash
kubectl apply -f k8s/namespace.yaml

# Verify
kubectl get namespace ml-system
```

Expected output:
```
NAME        STATUS   AGE
ml-system   Active   5s
```
Step 3 — Apply the ConfigMap
```bash
kubectl apply -f k8s/configmap.yaml

# Verify
kubectl get configmap -n ml-system
kubectl describe configmap iris-api-config -n ml-system
```
Step 4 — Apply the Deployment
```bash
kubectl apply -f k8s/deployment.yaml

# Watch pods come up in real time
kubectl get pods -n ml-system -w
```
You'll see pods go through: Pending → ContainerCreating → Running. Wait until the READY column shows 1/1 for both pods. Then press Ctrl+C to stop watching.
```bash
# Confirm both replicas are ready
kubectl get deployment iris-ml-api -n ml-system
```

Expected:
```
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
iris-ml-api    2/2     2            2           30s
```
If pods aren't becoming ready, check what's wrong:
```bash
# See events and probe results
kubectl describe pod -l app=iris-ml-api -n ml-system

# See container logs
kubectl logs -l app=iris-ml-api -n ml-system
```
Step 5 — Apply the Service
```bash
kubectl apply -f k8s/service.yaml

# Verify both services were created
kubectl get svc -n ml-system
```

Expected:
```
NAME                    TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)
iris-ml-api             ClusterIP      10.96.x.x       <none>        80/TCP
iris-ml-api-external    LoadBalancer   10.96.x.x       <pending>     80:30080/TCP
```
The EXTERNAL-IP will stay <pending> until you run minikube tunnel (see access step below).

Step 6 — Apply the HPA
```bash
kubectl apply -f k8s/hpa.yaml

# Verify
kubectl get hpa -n ml-system
```

Expected:
```
NAME               REFERENCE              TARGETS   MINPODS   MAXPODS   REPLICAS
iris-ml-api-hpa    Deployment/iris-ml-api  5%/70%    2         10        2
```
If you see <unknown>/70% under TARGETS, wait 60 seconds — metrics-server needs time to collect its first data points.

Step 7 — Apply the Ingress
```bash
kubectl apply -f k8s/ingress.yaml

# Verify
kubectl get ingress -n ml-system
```
Step 8 — Access the API
You have three options depending on your setup:
Option A — Port-forward (easiest, works always):
bashkubectl port-forward svc/iris-ml-api 8080:80 -n ml-system

# In a second terminal:
curl http://localhost:8080/health
Option B — NodePort (no tunnel needed):
```bash
# Get minikube's IP
minikube ip
# e.g. 192.168.49.2

curl http://192.168.49.2:30080/health
```
Option C — LoadBalancer via minikube tunnel:
```bash
# Run in a separate terminal (keep it open)
minikube tunnel

# Back in your main terminal
curl http://localhost:80/health
```
Step 9 — Verify everything is healthy
```bash
# All resources at a glance
kubectl get all -n ml-system

# Detailed deployment status
kubectl rollout status deployment/iris-ml-api -n ml-system

# Pod resource usage (requires metrics-server)
kubectl top pods -n ml-system

# Test a prediction (assuming port-forward is running)
curl -X POST http://localhost:8080/predict \
     -H "Content-Type: application/json" \
     -d '{"features": [5.1, 3.5, 1.4, 0.2]}'
```
What to do if something goes wrong
SymptomCommand to diagnosePod stuck in Pendingkubectl describe pod <name> -n ml-system → look for "Insufficient cpu/memory"Pod in CrashLoopBackOffkubectl logs <pod-name> -n ml-system --previousImagePullBackOffminikube image ls | grep iris — image not loadedHPA shows <unknown>minikube addons enable metrics-server then wait 60sService EXTERNAL-IP stuck on <pending>Run minikube tunnel in a separate terminalIngress not routingkubectl describe ingress -n ml-system — check events