<h1 align=center>K8s Commands</h1>

#### ✅ Apply all your new YAML files

#### 🧹 Delete old Kubernetes resources

#### 🗑️ Delete the entire namespace cleanly


## ✅ 1. Run (Apply) All Your Files

Make sure you're in the folder containing:
```bash
deployment.yaml
service.yaml
hpa.yaml
pdb.yaml
configmap.yaml
ingress.yaml
Apply everything at once:
kubectl apply -f .
```
Or apply individually:
```bash
kubectl apply -f configmap.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml
kubectl apply -f pdb.yaml
kubectl apply -f ingress.yaml
```
🔎 Verify Everything Is Running
```bash
kubectl get pods -n ml-system
kubectl get svc -n ml-system
kubectl get hpa -n ml-system
kubectl get ingress -n ml-system
```
Watch pods live:

kubectl get pods -n ml-system -w
🧹 2. Delete Old Kubernetes Resources (but keep namespace)

If you previously deployed older versions in ml-system:

Delete everything in that namespace:
```bash
kubectl delete all --all -n ml-system
```
⚠️ This deletes:
```bash
Pods

Deployments

ReplicaSets

Services

HPA

But NOT:

ConfigMaps

Secrets

PVCs

Ingress

PDB
```
If you want to delete absolutely everything inside the namespace:

kubectl delete all,configmap,secret,ingress,pvc,pdb --all -n ml-system
🗑️ 3. Delete the Entire Namespace (Clean Reset)

If you want a full wipe:
```bash
kubectl delete namespace ml-system
```
Check deletion progress:
```bash
kubectl get ns
```
If namespace gets stuck in "Terminating", tell me — I’ll give you the forced cleanup fix.

🔄 4. Recreate Namespace

After deleting:
```bash
kubectl create namespace ml-system
```
Then re-apply everything:
```bash
kubectl apply -f .
```
🔥 Quick Clean Reset (Recommended)

If you just want a clean slate:
```bash
kubectl delete namespace ml-system
kubectl create namespace ml-system
kubectl apply -f .
```
🧠 Pro Tip

To see everything currently running:
```bash
kubectl get all -A
```
To see which cluster you're connected to:
```bash
kubectl config current-context
```
==========================
==========================