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