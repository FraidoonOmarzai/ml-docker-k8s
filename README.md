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