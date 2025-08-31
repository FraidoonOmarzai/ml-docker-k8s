# ML Model Deployment with Docker & Kubernetes

A complete machine learning project demonstrating containerization with Docker and orchestration with Kubernetes.


## Steps:
1. create env, define template and install required packages
```bash
conda create -p mlenv python==3.11 -y
conda activate C:\Users\44787\Desktop\ml-docker-k8s\mlenv
python template.py
pip install -r requirements.txt
```
2. run `train_model.py`
3. 

## 🎯 Project Overview

This project implements a Random Forest classifier that:
- Trains on synthetic classification data
- Serves predictions via a REST API
- Runs in Docker containers
- Deploys on Kubernetes with high availability

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Init Container │    │   ML API Pod    │    │   ML API Pod    │
│  (Model Trainer) │───▶│  (Flask API)    │    │  (Flask API)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                └────────┬───────────────┘
                                         │
                                ┌─────────────────┐
                                │  Load Balancer  │
                                │   (K8s Service) │
                                └─────────────────┘
```

## 📁 Project Structure

```
ml-docker-k8s/
├── train_model.py          # ML model training script
├── app.py                  # Flask API service
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Local development setup
├── ml-deployment.yaml      # Kubernetes deployment
├── ml-config.yaml          # K8s ConfigMap & Secrets
├── setup.sh               # Automated setup script
└── README.md              # This file
```

## 🚀 Quick Start

### Prerequisites
- Docker installed
- Kubernetes cluster (minikube, kind, or cloud)
- kubectl configured
- curl for testing

### Option 1: Docker Compose (Local Development)

```bash
# Clone and navigate to project
cd ml-docker-k8s

# Build and run with Docker Compose
docker-compose up -d

# Test the API
curl http://localhost:5000/health
```

### Option 2: Kubernetes Deployment

```bash
# Run the automated setup
chmod +x setup.sh
./setup.sh

# Or manually:
docker build -t ml-model:latest .
kubectl apply -f ml-config.yaml
kubectl apply -f ml-deployment.yaml
```

## 🔧 API Endpoints

### Health Check
```bash
GET /health
```

### Model Information
```bash
GET /model-info
```

### Make Predictions
```bash
POST /predict
Content-Type: application/json

{
  "features": [0.1, 0.2, 0.3, ..., 2.0]  # 20 feature values
}
```

## 📊 Example Usage

```bash
# Test prediction
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 
                 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
  }'

# Response:
{
  "prediction": 1,
  "probabilities": {
    "class_0": 0.23,
    "class_1": 0.65,
    "class_2": 0.12
  },
  "timestamp": "2025-08-31T10:30:00"
}
```

## ☸️ Kubernetes Features

- **High Availability**: 3 replica pods with load balancing
- **Init Containers**: Model training runs before API containers
- **Health Checks**: Liveness and readiness probes
- **Resource Management**: CPU and memory limits
- **ConfigMaps**: Environment-specific configuration
- **Secrets**: Secure API key storage
- **Ingress**: External access configuration

## 🔍 Monitoring & Debugging

```bash
# View pod status
kubectl get pods -l app=ml-model

# Check logs
kubectl logs -l app=ml-model -f

# Describe deployment
kubectl describe deployment ml-model-deployment

# Scale the deployment
kubectl scale deployment ml-model-deployment --replicas=5

# Access pod directly
kubectl exec -it <pod-name> -- /bin/bash
```

## 🛠️ Development Workflow

1. **Local Development**: Use Docker Compose for quick iteration
2. **Testing**: Build and test Docker image locally
3. **Staging**: Deploy to development Kubernetes cluster
4. **Production**: Deploy to production cluster with proper secrets

## 📈 Scaling Considerations

- **Horizontal Scaling**: Increase replica count for more traffic
- **Resource Tuning**: Adjust CPU/memory based on workload
- **Model Storage**: Use persistent volumes for larger models
- **Caching**: Add Redis for frequent predictions
- **Monitoring**: Integrate Prometheus for metrics

## 🔒 Security Features

- Non-root container execution
- Resource limits to prevent resource exhaustion
- Health checks for automatic recovery
- Secrets management for sensitive data
- Network policies (can be added)

## 🚀 Next Steps

- Add model versioning and A/B testing
- Implement model monitoring and drift detection
- Add CI/CD pipeline with automated testing
- Integrate with model registry (MLflow, etc.)
- Add logging and metrics collection
- Implement blue-green deployments

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes and test locally
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details