# Ops Cheatsheet — ML API on Kubernetes

> Every command you'll need, organised by scenario.

---

## 0. Setup — Start Fresh

```bash
# Start minikube (local cluster)
minikube start --cpus=4 --memory=4g
```

---

## 1. First Deploy

```bash
# Full deploy (train → build → apply manifests)
chmod +x k8s_deploy.sh && ./k8s_deploy.sh

# Windows:
.\k8s_deploy.ps1

# Dry-run first to validate manifests
./k8s_deploy.sh --dry-run
.\k8s_deploy.ps1 ...

# Apply a single manifest
kubectl apply -f k8s/deployment.yaml
```

---

## 2. Accessing the API

```bash
# Option A — Port-forward (easiest, no DNS needed)
kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace
# Then: curl http://localhost:8080/health

# ... other options
```

---

## 3. Rolling Update (Zero Downtime)

```bash
# Step 1 — Retrain with new model / code changes, rebuild image
python model/train.py
docker build -t fraidoonjan/dock8s:v2 .

# Step 2 — Load new image into minikube
minikube image load fraidoonjan/dock8s:v2

# Step 3 — Update the deployment image (triggers rolling update)
kubectl set image deployment/dock8s-api \
    dock8s-api=fraidoonjan/dock8s:v2 \
    -n dock8s-namespace

# Step 4 — Watch the rollout happen live
kubectl rollout status deployment/dock8s-api -n dock8s-namespace

# Check rollout history
kubectl rollout history deployment/dock8s-api -n dock8s-namespace
```

---

## 4. Rollback

```bash
# Roll back to previous revision
./ops/rollback.sh

# Roll back to a specific revision number
./ops/rollback.sh --to-revision=2

# Skip confirmation (CI/CD use)
./ops/rollback.sh --force

# Windows:
.\ops\rollback.ps1
.\ops\rollback.ps1 -ToRevision 2
.\ops\rollback.ps1 -Force

# Raw kubectl rollback (no confirmation)
kubectl rollout undo deployment/dock8s-api -n dock8s-namespace
kubectl rollout undo deployment/dock8s-api -n dock8s-namespace --to-revision=2
```

---

## 5. Scaling

```bash
# Manual scale — set exact replica count
kubectl scale deployment dock8s-api --replicas=5 -n dock8s-namespace

# Watch pods come up
kubectl get pods -n dock8s-namespace -w

# Check HPA status (auto-scaling)
kubectl get hpa -n dock8s-namespace
kubectl describe hpa dock8s-api-hpa -n dock8s-namespace

# Trigger HPA by running load test (in one terminal)
kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace

# Then in another terminal:
python ops/load_test.py --rps 100 --duration 120 --workers 20

# Watch HPA and pods respond in real-time (third terminal)
kubectl get hpa -n dock8s-namespace -w
kubectl get pods -n dock8s-namespace-w
```

---

## 6. Live Verification

```bash
# Full deployment health check (kubectl + API + latency)
python ops/verify_deployment.py

# API-only (no kubectl access needed)
python ops/verify_deployment.py --skip-kubectl

# Against any URL
python ops/verify_deployment.py --url http://dock8s-api.local

# Quick one-liner health check
curl -s http://localhost:8080/health | python3 -m json.tool

# Batch prediction test
curl -s -X POST http://localhost:8080/predict/batch \
     -H "Content-Type: application/json" \
     -d '{"features": [[5.1,3.5,1.4,0.2],[6.7,3.0,5.2,2.3]]}' \
     | python3 -m json.tool
```

---

## 7. Logs & Debugging

```bash
# Stream logs from ALL replicas simultaneously
kubectl logs -l app=dock8s-api -n dock8s-namespace -f --tail=50

# Logs from one specific pod
kubectl logs <pod-name> -n dock8s-namespace -f

# Previous container's logs (if pod restarted)
kubectl logs <pod-name> -n dock8s-namespace --previous

# Describe pod (events, resource usage, probe results)
kubectl describe pod -l app=dock8s-api -n dock8s-namespace

# Describe deployment (rollout events, conditions)
kubectl describe deployment dock8s-api -n dock8s-namespace

# Shell into a running pod
kubectl exec -it <pod-name> -n dock8s-namespace -- /bin/sh

# Check resource usage (requires metrics-server)
kubectl top pods -n dock8s-namespace
kubectl top nodes
```

---

## 8. ConfigMap Updates

```bash
# Edit ConfigMap live
kubectl edit configmap dock8s-api-config -n dock8s-namespace

# Or apply updated file
kubectl apply -f k8s/configmap.yaml

# Force pod restart to pick up ConfigMap changes
kubectl rollout restart deployment/dock8s-api -n dock8s-namespace

# Watch restart progress
kubectl rollout status deployment/dock8s-api -n dock8s-namespace
```

---

## 9. Troubleshooting

```bash
# Pod stuck in Pending?
kubectl describe pod <pod-name> -n dock8s-namespace
# → look for: Insufficient cpu/memory, image pull errors, unschedulable

# Pod in CrashLoopBackOff?
kubectl logs <pod-name> -n dock8s-namespace --previous
# → model artifacts missing? wrong ARTIFACTS_DIR? OOM?

# ImagePullBackOff?
# → image name wrong, not loaded into minikube, registry auth missing
minikube image ls | grep iris      # verify image exists

# HPA not scaling?
kubectl describe hpa dock8s-api-hpa -n dock8s-namespace
# → metrics-server not running? requests not set in deployment?
minikube addons enable metrics-server

# Service not routing?
kubectl get endpoints dock8s-api -n dock8s-namespace
# → should show pod IPs; if empty, selector labels may not match

# Port-forward failing?
kubectl get pods -n dock8s-namespace   # is there at least one Running pod?
```

---

## 10. Tear Down

```bash
# Delete all resources in the namespace (keeps namespace)
kubectl delete deployment,svc,hpa,ingress,configmap \
    -l app=dock8s-api -n dock8s-namespace

# Delete the entire namespace (removes everything)
kubectl delete namespace dock8s-namespace

# Stop minikube
minikube stop

# Delete minikube cluster entirely
minikube delete
```

---

## Quick Reference Card

| Goal           | Command                                                                                |
| -------------- | -------------------------------------------------------------------------------------- |
| Deploy         | `./k8s_deploy.sh`                                                                      |
| Port-forward   | `kubectl port-forward svc/dock8s-api 8080:80 -n dock8s-namespace`                      |
| Verify         | `python ops/verify_deployment.py`                                                      |
| Load test      | `python ops/load_test.py --rps 50 --duration 60`                                       |
| Watch pods     | `kubectl get pods -n dock8s-namespace -w`                                              |
| Watch HPA      | `kubectl get hpa -n dock8s-namespace -w`                                               |
| Logs           | `kubectl logs -l app=dock8s-api -n dock8s-namespace -f`                                |
| Scale to 4     | `kubectl scale deployment dock8s-api --replicas=4 -n dock8s-namespace`                 |
| Rolling update | `kubectl set image deployment/dock8s-api dock8s-api=dock8s-api:v2 -n dock8s-namespace` |
| Rollback       | `./ops/rollback.sh`                                                                    |
| Restart pods   | `kubectl rollout restart deployment/dock8s-api -n dock8s-namespace`                    |
| Shell into pod | `kubectl exec -it <pod> -n dock8s-namespace -- /bin/sh`                                |
| Resource usage | `kubectl top pods -n dock8s-namespace`                                                 |
| Delete all     | `kubectl delete namespace dock8s-namespace`                                            |
