

```bash
minikube start
```

###  🚀 How to Use (Docker + k8s)
#### 1️⃣ Build & Push Docker Image
```bash
docker build -t your-dockerhub-username/ml-api:latest .
docker push your-dockerhub-username/ml-api:latest
```
#### 2️⃣ Deploy to Kubernetes
```bash
kubectl apply -f k8s-deployment.yaml
kubectl apply -f k8s-service.yaml
```
#### 3️⃣ Access App
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




#### Important commands k8s
```bash
kubectl get namespaces

kubectl get pods -n dock8s-namespace


```


