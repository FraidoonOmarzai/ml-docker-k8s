<h1 align=center>K8s Details DES</h1>

## How to Use (Docker + k8s)

`Below are step by step process to run Docker + k8s`

- Before running your YAML files, make sure you have:

### ✅ Installed tools

- Docker (for building images)
- kubectl (to interact with cluster)
- Minikube or a real cluster (EKS, GKE, AKS)

1. Check cluster status

- Run:

```bash
kubectl cluster-info
```

If you see the same error → cluster is NOT running

2. Start your cluster

- If using Minikube:

```bash
minikube start
```

- Then verify:

```bash
kubectl get nodes
```

- You should see something like:

```
minikube   Ready
```

👉 If using Docker Desktop Kubernetes:

```
Open Docker Desktop → enable Kubernetes → wait until it's running.
```

👉 If using cloud (EKS/GKE/AKS):

- Make sure credentials are set:

```
kubectl config get-contexts
kubectl config use-context <your-cluster>
```

---

---

### 🧱 1. Build your Docker image

Go to your project root (where your Dockerfile is):

```bash
docker build -t fraidoonjan/dock8s:latest .
```

👉 This creates your app image.

### 📦 2. Make image available to Kubernetes

#### Option A — If using Minikube (local)

Run:

```bash
minikube image load fraidoonjan/dock8s:latest
```

- OR build inside Minikube:

```bash
eval $(minikube docker-env)
docker build -t fraidoonjan/dock8s:latest .
```

#### Option B — If using cloud (EKS/GKE/etc.)

- Push to registry:

```bash
docker tag dock8s:latest your-dockerhub-username/dock8s:latest
docker push your-dockerhub-username/dock8s:latest # mine is fraidoonjan/dock8s:latest
```

Then use that image name in `deployment.yaml`.

`Note:` Simply we can build a docker image, push it to docker hub and later on we can use it inside doployment.yaml.

```bash
docker build -t your-dockerhub-username/dock8s:latest .
docker push your-dockerhub-username/dock8s:latest
```

### ⚙️ 3. Update your deployment.yaml

- Make sure it points to your image:

```bash
containers:
  - name: dock8s-api
    image: fraidoonjan/dock8s # DockerHub image
    imagePullPolicy: IfNotPresent # Always
```

### 🧩 4. Apply Kubernetes files (in order)

- Navigate to your k8s/ folder:

```bash
cd k8s

## Apply everything step by step:
# Step 1 — Apply namespace
kubectl apply -f namespace.yaml
# Verify
kubectl get namespace dock8s-namespace

# Step 2 — Apply the ConfigMap
kubectl apply -f configmap.yaml
# Verify
kubectl get configmap -n dock8s-namespace
kubectl describe configmap dock8s-api-config -n dock8s-namespace

# Step 3 — Apply the Deployment
kubectl apply -f deployment.yaml
## Watch pods come up in real time
kubectl get pods -n dock8s-namespace -w
# You'll see pods go through: Pending → ContainerCreating → Running. Wait until the READY column shows 1/1 for both pods. Then press Ctrl+C to stop watching.
# Confirm replicas are ready
kubectl get deployment dock8s-api -n dock8s-namespace

# Step 4 — Apply the Service
kubectl apply -f service.yaml
# Verify both services were created
kubectl get svc -n dock8s-namespace
# Expected Output
NAME                 TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
api-service          LoadBalancer   10.102.17.147   <pending>     80:30309/TCP   40d
dock8s-api-service   LoadBalancer   10.101.44.63    <pending>     80:32670/TCP   31d

# Step 5 — Apply the HPA
kubectl apply -f hpa.yaml
# Verify
kubectl get hpa -n dock8s-namespace


# Step 6 — Apply the Ingress
kubectl apply -f ingress.yaml
# Verify
kubectl get ingress -n dock8s-namespace
```

### 5. Access the API

```bash
kubectl get nodes -o wide
```

- Then open:

```bash
http://<NODE-IP>:30007
```

- The above access app work for the below svc

```bash
apiVersion: v1
kind: Service
metadata:
  name: ml-api-service
spec:
  type: NodePort
  selector:
    app: ml-api
  ports:
    - port: 80
      targetPort: 8000
      nodePort: 30007
```

- if we get the below code for our project we face with that problem:

```bash
---
apiVersion: v1
kind: Service
metadata:
  name: dock8s-api-service
  namespace: dock8s-namespace
spec:
  type: LoadBalancer
  # type: NodePort
  selector:
    app: dock8s-api
  ports:
  - port: 80
    targetPort: 8080
```

#### Why <pending> Happens

LoadBalancer only works automatically in cloud Kubernetes providers, like:

```bash
## AWS EKS
## Google GKE
## Azure AKS

# Those create a real external load balancer.
# Local clusters cannot create one, so the IP stays <pending>.
```

- Fastest working command for you right now:

```bash
kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace
```

- Then open:

```bash
http://localhost:8080
```

---

---

### Access the api: You have three options depending on your setup:

Option A — Port-forward (easiest, works always):

```bash
kubectl port-forward svc/dock8s-api-service 8080:80 -n dock8s-namespace
```

- In a second terminal:
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

---

---

### Verify Everything is healthy

```bash
# All resources at a glance
kubectl get all -n dock8s-namespace

# Detailed deployment status
kubectl rollout status deployment/dock8s-api -n dock8s-namespace

# Pod resource usage (requires metrics-server)
kubectl top pods -n dock8s-namespace
```

# ==========================

## K8s Commands

- Watch pods live:

```bash
kubectl get pods -n dock8s-namespace -w
```

- Delete Old Kubernetes Resources (but keep namespace)

- Delete everything in that namespace:

```bash
kubectl delete all --all -n ml-system
```

⚠️ This deletes:

```bash
Pods

Deployments

ReplicaSets

Services

But NOT:

ConfigMaps

Secrets

PVCs

Ingress

PDB
```

- If you want to delete absolutely everything inside the namespace:

- kubectl delete all,configmap,secret,ingress,pvc,pdb --all -n dock8s-namespace
- Delete the Entire Namespace (Clean Reset)

- If you want a full wipe:

```bash
kubectl delete namespace dock8s-namespace
```

- Check deletion progress:

```bash
kubectl get ns
```

- If namespace gets stuck in "Terminating", tell me — I’ll give you the forced cleanup fix.

- Recreate Namespace

- After deleting:

```bash
kubectl create namespace dock8s-namespace
```

- Then re-apply everything:

```bash
kubectl apply -f .
```

#### Quick Clean Reset (Recommended)

- If you just want a clean slate:

```bash
kubectl delete namespace dock8s-namespace
kubectl create namespace dock8s-namespace
kubectl apply -f .
```

🧠 Pro Tip

- To see everything currently running:

```bash
kubectl get all -A
```

- To see which cluster you're connected to:

```bash
kubectl config current-context
```

# ==========================

## Simple k8s section

```
ml-k8s-project/
└── k8s/
    ├── namespace.yaml          ← isolated environment
    ├── deployment.yaml         ← pods, replicas, probes, resources
    ├── service.yaml            ← internal + external networking
```

- `deployment.yaml` file along with `service.yaml` file in a single file

```bash
# ─────────────────────────────────────────────────────────────────────────────
# deployment.yaml
# Defines how our ML API pods are created, updated, and kept healthy.
#
# ─────────────────────────────────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dock8s-api
  namespace: dock8s-namespace
  labels:
    app: dock8s-api
spec:
  replicas: 1

  selector:
    matchLabels:
      app: dock8s-api

  template:
    metadata:
      labels:
        app: dock8s-api

    spec:

      containers:
        - name: dock8s-api
          image: fraidoonjan/dock8s
          imagePullPolicy: Always

          ports:
            - containerPort: 8080

          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 20
            periodSeconds: 15

          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 10

          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"

---
apiVersion: v1
kind: Service
metadata:
  name: dock8s-api-service
  namespace: dock8s-namespace
spec:
  type: LoadBalancer
  # type: NodePort
  selector:
    app: dock8s-api
  ports:
  - port: 80
    targetPort: 8080
```

- `namespace.yaml` file

```bash
# ─────────────────────────────────────────────────────────────────────────────
# namespace.yaml
# Creates an isolated namespace for all ML system resources.
# Best practice: never deploy to `default` in production.
# ─────────────────────────────────────────────────────────────────────────────
apiVersion: v1
kind: Namespace
metadata:
  name: dock8s-namespace
  labels:
    name: dock8s-namespace
    app.kubernetes.io/name: dock8s-namespace
```

---

---

---
