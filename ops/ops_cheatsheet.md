# Ops Cheatsheet — Iris ML API on Kubernetes
> Every command you'll need, organised by scenario.

---

## 0. Setup — Start Fresh

```bash
# Start minikube (local cluster)
minikube start --cpus=4 --memory=4g
minikube addons enable ingress
minikube addons enable metrics-server   # required for HPA

# Point your shell to minikube's Docker daemon (Linux/Mac)
eval $(minikube docker-env)

# Windows PowerShell:
# & minikube -p minikube docker-env | Invoke-Expression
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
.\k8s_deploy.ps1 -DryRun

# Apply a single manifest
kubectl apply -f k8s/deployment.yaml
```

---

## 2. Accessing the API

```bash
# Option A — Port-forward (easiest, no DNS needed)
kubectl port-forward svc/iris-ml-api 8080:80 -n ml-system
# Then: curl http://localhost:8080/health

# Option B — minikube service URL (opens browser)
minikube service iris-ml-api-external -n ml-system --url

# Option C — NodePort direct
export MINIKUBE_IP=$(minikube ip)
curl http://$MINIKUBE_IP:30080/health

# Option D — Ingress (add to /etc/hosts first)
echo "$(minikube ip) iris-api.local" | sudo tee -a /etc/hosts
curl http://iris-api.local/health

# Windows hosts file: C:\Windows\System32\drivers\etc\hosts
# Add: <minikube-ip> iris-api.local
```

---

## 3. Rolling Update (Zero Downtime)

```bash
# Step 1 — Retrain with new model / code changes, rebuild image
python model/train.py
docker build -t iris-ml-api:v2 .

# Step 2 — Load new image into minikube
minikube image load iris-ml-api:v2

# Step 3 — Update the deployment image (triggers rolling update)
kubectl set image deployment/iris-ml-api \
    iris-ml-api=iris-ml-api:v2 \
    -n ml-system

# Step 4 — Watch the rollout happen live
kubectl rollout status deployment/iris-ml-api -n ml-system

# Check rollout history
kubectl rollout history deployment/iris-ml-api -n ml-system
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
kubectl rollout undo deployment/iris-ml-api -n ml-system
kubectl rollout undo deployment/iris-ml-api -n ml-system --to-revision=2
```

---

## 5. Scaling

```bash
# Manual scale — set exact replica count
kubectl scale deployment iris-ml-api --replicas=5 -n ml-system

# Watch pods come up
kubectl get pods -n ml-system -w

# Check HPA status (auto-scaling)
kubectl get hpa -n ml-system
kubectl describe hpa iris-ml-api-hpa -n ml-system

# Trigger HPA by running load test (in one terminal)
kubectl port-forward svc/iris-ml-api 8080:80 -n ml-system

# Then in another terminal:
python ops/load_test.py --rps 100 --duration 120 --workers 20

# Watch HPA and pods respond in real-time (third terminal)
kubectl get hpa -n ml-system -w
kubectl get pods -n ml-system -w
```

---

## 6. Live Verification

```bash
# Full deployment health check (kubectl + API + latency)
python ops/verify_deployment.py

# API-only (no kubectl access needed)
python ops/verify_deployment.py --skip-kubectl

# Against any URL
python ops/verify_deployment.py --url http://iris-api.local

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
kubectl logs -l app=iris-ml-api -n ml-system -f --tail=50

# Logs from one specific pod
kubectl logs <pod-name> -n ml-system -f

# Previous container's logs (if pod restarted)
kubectl logs <pod-name> -n ml-system --previous

# Describe pod (events, resource usage, probe results)
kubectl describe pod -l app=iris-ml-api -n ml-system

# Describe deployment (rollout events, conditions)
kubectl describe deployment iris-ml-api -n ml-system

# Shell into a running pod
kubectl exec -it <pod-name> -n ml-system -- /bin/sh

# Check resource usage (requires metrics-server)
kubectl top pods -n ml-system
kubectl top nodes
```

---

## 8. ConfigMap Updates

```bash
# Edit ConfigMap live
kubectl edit configmap iris-api-config -n ml-system

# Or apply updated file
kubectl apply -f k8s/configmap.yaml

# Force pod restart to pick up ConfigMap changes
kubectl rollout restart deployment/iris-ml-api -n ml-system

# Watch restart progress
kubectl rollout status deployment/iris-ml-api -n ml-system
```

---

## 9. Troubleshooting

```bash
# Pod stuck in Pending?
kubectl describe pod <pod-name> -n ml-system
# → look for: Insufficient cpu/memory, image pull errors, unschedulable

# Pod in CrashLoopBackOff?
kubectl logs <pod-name> -n ml-system --previous
# → model artifacts missing? wrong ARTIFACTS_DIR? OOM?

# ImagePullBackOff?
# → image name wrong, not loaded into minikube, registry auth missing
minikube image ls | grep iris      # verify image exists

# HPA not scaling?
kubectl describe hpa iris-ml-api-hpa -n ml-system
# → metrics-server not running? requests not set in deployment?
minikube addons enable metrics-server

# Service not routing?
kubectl get endpoints iris-ml-api -n ml-system
# → should show pod IPs; if empty, selector labels may not match

# Port-forward failing?
kubectl get pods -n ml-system    # is there at least one Running pod?
```

---

## 10. Tear Down

```bash
# Delete all resources in the namespace (keeps namespace)
kubectl delete deployment,svc,hpa,ingress,configmap \
    -l app=iris-ml-api -n ml-system

# Delete the entire namespace (removes everything)
kubectl delete namespace ml-system

# Stop minikube
minikube stop

# Delete minikube cluster entirely
minikube delete
```

---

## Quick Reference Card

| Goal | Command |
|------|---------|
| Deploy | `./k8s_deploy.sh` |
| Port-forward | `kubectl port-forward svc/iris-ml-api 8080:80 -n ml-system` |
| Verify | `python ops/verify_deployment.py` |
| Load test | `python ops/load_test.py --rps 50 --duration 60` |
| Watch pods | `kubectl get pods -n ml-system -w` |
| Watch HPA | `kubectl get hpa -n ml-system -w` |
| Logs | `kubectl logs -l app=iris-ml-api -n ml-system -f` |
| Scale to 4 | `kubectl scale deployment iris-ml-api --replicas=4 -n ml-system` |
| Rolling update | `kubectl set image deployment/iris-ml-api iris-ml-api=iris-ml-api:v2 -n ml-system` |
| Rollback | `./ops/rollback.sh` |
| Restart pods | `kubectl rollout restart deployment/iris-ml-api -n ml-system` |
| Shell into pod | `kubectl exec -it <pod> -n ml-system -- /bin/sh` |
| Resource usage | `kubectl top pods -n ml-system` |
| Delete all | `kubectl delete namespace ml-system` |