# Phase 6 — Monitoring & Observability

> **Goal:** Make the ML API fully observable — know what it's doing, how fast, and get alerted before users notice problems.

---

## Table of Contents

1. [What Was Built](#what-was-built)
2. [How It All Fits Together](#how-it-all-fits-together)
3. [File Breakdown](#file-breakdown)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [What the Metrics Mean](#what-the-metrics-mean)
6. [Reading the Logs](#reading-the-logs)
7. [Understanding the Alerts](#understanding-the-alerts)
8. [Using the Grafana Dashboard](#using-the-grafana-dashboard)
9. [Useful PromQL Queries](#useful-promql-queries)
10. [Troubleshooting](#troubleshooting)

---

## What Was Built

| File | What it does |
|------|-------------|
| `app/metrics.py` | Defines every Prometheus metric the API tracks |
| `app/main.py` | Updated to record metrics on every request + structured JSON logs |
| `monitoring/prometheus-config.yaml` | Tells Prometheus to scrape our API + pre-computed recording rules |
| `monitoring/alerts.yaml` | 9 alerting rules (downtime, latency, errors, pod health) |
| `monitoring/grafana-dashboard.json` | Importable 11-panel Grafana dashboard |
| `monitoring/setup_monitoring.sh` | One-command install of the full Prometheus + Grafana stack |

---

## How It All Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                    │
│                                                         │
│  ┌──────────────┐     scrapes      ┌─────────────────┐  │
│  │  Dock8s-ml-api │ ◄─────────────── │   Prometheus    │  │
│  │  /metrics    │   every 15s      │                 │  │
│  └──────────────┘                  │  + Alertmanager │  │
│         │                          └────────┬────────┘  │
│         │ JSON logs                         │ queries   │
│         ▼                                   ▼           │
│  ┌──────────────┐                  ┌─────────────────┐  │
│  │  stdout      │                  │    Grafana      │  │
│  │  (ELK/Loki)  │                  │   Dashboard     │  │
│  └──────────────┘                  └─────────────────┘  │
│                                             │            │
│                                    fires alerts          │
│                                             ▼            │
│                                    Slack / PagerDuty     │
└─────────────────────────────────────────────────────────┘
```

The API exposes a `/metrics` endpoint. Prometheus scrapes it every 15 seconds and stores the data as time series. Grafana reads from Prometheus and displays the dashboard. Alertmanager watches Prometheus for rule violations and fires notifications.

---

## File Breakdown

### `app/metrics.py`

This file defines all the Prometheus metric objects. They are grouped into three layers:

**HTTP metrics** — track every request regardless of what it does:
- `Dock8s_api_requests_total` — counts every request, labelled by method, endpoint, and status code
- `Dock8s_api_request_duration_seconds` — histogram of how long each request took
- `Dock8s_api_requests_in_progress` — live count of requests currently being handled

**Inference metrics** — track what the model actually does:
- `Dock8s_api_predictions_total` — count of predictions, labelled by class (setosa/versicolor/virginica)
- `Dock8s_api_prediction_duration_seconds` — time spent inside model `.predict()` only, excluding HTTP overhead
- `Dock8s_api_prediction_confidence` — histogram of the model's max probability score per prediction
- `Dock8s_api_batch_size` — histogram of batch sizes sent to `/predict/batch`

**Error metrics** — track what goes wrong:
- `Dock8s_api_prediction_errors_total` — runtime errors during inference
- `Dock8s_api_validation_errors_total` — bad input (422 responses)

**Model health:**
- `Dock8s_api_model_loaded` — Gauge that is `1` when model is healthy, `0` when not
- `Dock8s_api_model` — Info metric with static labels: model type, accuracy, version

---

### `app/main.py` (updated)

Two things were added on top of the Phase 2 version:

**Metrics middleware** — a single middleware function wraps every HTTP request. Before the request runs it increments `requests_in_progress`. After it finishes it records the status code into `requests_total` and the duration into `request_duration_seconds`. The `/metrics` endpoint itself is excluded from tracking to avoid noise.

**Structured JSON logging** — the plain text logger is replaced with a `JSONFormatter` class. Every log line is now a valid JSON object:

```json
{
  "timestamp": "2025-01-15T10:30:45",
  "level": "INFO",
  "logger": "app.main",
  "message": "request",
  "service": "Dock8s-ml-api",
  "version": "1.0.0",
  "env": "production",
  "http_method": "POST",
  "http_path": "/predict",
  "http_status": 200,
  "duration_ms": 12.4
}
```

JSON logs can be ingested directly by ELK Stack, Grafana Loki, Datadog, or any log aggregator without custom parsing rules.

---

### `monitoring/prometheus-config.yaml`

Contains two Kubernetes custom resources (CRDs provided by Prometheus Operator):

**ServiceMonitor** — instead of editing a static Prometheus config file, this CRD tells the Prometheus Operator "watch for services with the label `app: Dock8s-ml-api` and scrape their `/metrics` endpoint every 15 seconds". When you deploy a new pod, Prometheus picks it up automatically.

**PrometheusRule (Recording Rules)** — raw Prometheus counters require expensive PromQL at query time. Recording rules pre-compute them into new time series every 15 seconds so Grafana queries are instant:

| Recording Rule | What it computes |
|---------------|-----------------|
| `Dock8s_api:request_rate5m` | Requests per second (5m window) per endpoint |
| `Dock8s_api:error_rate5m` | Fraction of requests returning non-2xx |
| `Dock8s_api:latency_p95_5m` | 95th percentile request latency |
| `Dock8s_api:latency_p99_5m` | 99th percentile request latency |
| `Dock8s_api:prediction_rate5m` | Predictions per second by class |
| `Dock8s_api:avg_confidence5m` | Average model confidence by class |
| `Dock8s_api:inference_latency_avg5m` | Average pure model inference time |

---

### `monitoring/alerts.yaml`

Nine alerting rules across four groups. Each alert has a `severity` (warning or critical), a `team` label for routing, and an `annotations.description` with context.

| Alert | Condition | Severity |
|-------|-----------|----------|
| `Dock8sAPIDown` | `model_loaded` metric missing for 1 min | critical |
| `Dock8sAPIHighErrorRate` | 5xx rate > 5% for 3 min | critical |
| `Dock8sAPIHighValidationErrors` | > 10 validation errors/sec for 5 min | warning |
| `Dock8sAPIHighP95Latency` | p95 > 500ms for 5 min | warning |
| `Dock8sAPIHighP99Latency` | p99 > 2s for 5 min | critical |
| `Dock8sAPISlowInference` | avg model inference > 100ms for 5 min | warning |
| `Dock8sAPINoTraffic` | 0 requests on /predict for 10 min | warning |
| `Dock8sAPIHighRequestRate` | > 500 rps for 2 min | warning |
| `Dock8sAPIPodCrashLooping` | > 3 restarts in 15 min | critical |
| `Dock8sAPILowReadyReplicas` | ready replicas < 1 for 2 min | critical |

---

### `monitoring/grafana-dashboard.json`

An importable JSON dashboard with 11 panels arranged in 4 rows:

**Row 1 — Status bar (5 stat panels):**
Model loaded status, current RPS, error rate percentage, p95 latency, ready replica count. Each panel has colour thresholds (green/yellow/red) so problems are immediately visible.

**Row 2 — Traffic & latency (2 time series):**
RPS broken down by endpoint over time, and a latency percentile chart showing p50/p95/p99 on one graph.

**Row 3 — Model behaviour (2 time series):**
Prediction counts by class (useful for detecting distribution shift — if versicolor suddenly spikes that's unusual), and model confidence over time per class.

**Row 4 — Detail panels (2 panels):**
HTTP status code donut chart for the past hour, and a model inference latency chart that separates pure model time from total request time so you can see HTTP overhead.

---

## Step-by-Step Setup

### Prerequisites

```bash
# You need Helm installed
# Mac:
brew install helm

# Windows:
winget install Helm.Helm

# Linux:
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

---

### Step 1 — Rebuild the Docker image

Phase 6 adds `prometheus-client` to `requirements-serve.txt` and updates `main.py`. You must rebuild:

```bash
# Point to minikube's Docker daemon
eval $(minikube docker-env)          # Linux/Mac
# Windows: & minikube -p minikube docker-env | Invoke-Expression

# Rebuild with the new code
docker build -t Dock8s-api:latest .

# Verify the new image is there
docker images | grep Dock8s
```

---

### Step 2 — Redeploy the API

```bash
# Restart pods so they pick up the new image
kubectl rollout restart deployment/Dock8s-ml-api -n Dock8s-namespace

# Wait for rollout
kubectl rollout status deployment/Dock8s-ml-api -n Dock8s-namespace

# Confirm pods are running
kubectl get pods -n Dock8s-namespace
```

---

### Step 3 — Verify the /metrics endpoint

Before installing Prometheus, confirm the endpoint is working:

```bash
# Open a port-forward in one terminal
kubectl port-forward svc/Dock8s-ml-api 8080:80 -n Dock8s-namespace

# In another terminal, hit the metrics endpoint
curl http://localhost:8080/metrics
```

You should see raw Prometheus output like:

```
# HELP Dock8s_api_requests_total Total HTTP requests received
# TYPE Dock8s_api_requests_total counter
Dock8s_api_requests_total{endpoint="/health",http_status="200",method="GET"} 3.0

# HELP Dock8s_api_model_loaded 1 if the model is loaded and ready, 0 otherwise
# TYPE Dock8s_api_model_loaded gauge
Dock8s_api_model_loaded 1.0
```

If you see this, the metrics layer is working correctly.

---

### Step 4 — Install Prometheus + Grafana via Helm

```bash
# Add the Helm chart repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install the full stack (Prometheus + Grafana + Alertmanager) into a new namespace
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
    --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
    --wait --timeout 5m
```

The two `--set` flags are important — they tell Prometheus to watch for `ServiceMonitor` resources in ALL namespaces, not just the one it was installed in.

Wait for all pods to be ready:

```bash
kubectl get pods -n monitoring -w
# Wait until all show Running 1/1
```

---

### Step 5 — Apply the ServiceMonitor and Alert rules

```bash
# Tell Prometheus to scrape our API
kubectl apply -f monitoring/prometheus-config.yaml

# Install the alerting rules
kubectl apply -f monitoring/alerts.yaml

# Verify
kubectl get servicemonitor -n Dock8s-namespace
kubectl get prometheusrule -n Dock8s-namespace
```

---

### Step 6 — Open Grafana

```bash
# Port-forward Grafana to your machine
kubectl port-forward svc/kube-prometheus-grafana 3000:80 -n monitoring
```

Open `http://localhost:3000` in your browser.

- **Username:** `admin`
- **Password:** `prom-operator`

---

### Step 7 — Import the dashboard

1. In Grafana, click the **+** icon in the left sidebar
2. Click **Import**
3. Click **Upload JSON file**
4. Select `monitoring/grafana-dashboard.json`
5. Select your Prometheus data source from the dropdown
6. Click **Import**

The dashboard will appear with all 11 panels. If some panels show "No data", generate some traffic first:

```bash
# In another terminal (port-forward must still be running)
python ops/load_test.py --rps 20 --duration 30
```

---

### Step 8 — Open Prometheus UI (optional)

```bash
kubectl port-forward svc/kube-prometheus-kube-prome-prometheus 9090:9090 -n monitoring
```

Open `http://localhost:9090`. You can run raw PromQL queries here to test your metrics before building Grafana panels.

---

### Step 9 — Open Alertmanager (optional)

```bash
kubectl port-forward svc/kube-prometheus-kube-prome-alertmanager 9093:9093 -n monitoring
```

Open `http://localhost:9093` to see active alerts and silences.

---

## What the Metrics Mean

### Difference between request latency and inference latency

There are two latency metrics and they measure different things:

- `Dock8s_api_request_duration_seconds` — total time from HTTP request received to response sent. Includes network, FastAPI routing, input validation, model inference, and response serialisation.
- `Dock8s_api_prediction_duration_seconds` — time spent only inside `pipeline.predict()`. Pure model time, no HTTP.

The difference between them is your HTTP overhead. If request p95 is 80ms and inference p95 is 5ms, then 75ms is being spent on everything except the model.

### What model confidence tells you

`Dock8s_api_prediction_confidence` records the highest probability the model assigned across the three classes for each prediction. A confidence of 0.98 means the model is very sure. A confidence of 0.42 means it barely picked one class over another.

If average confidence drops over time without a code change, it often means the incoming data is drifting away from the training distribution — a classic ML production problem called **data drift**.

### What prediction class distribution tells you

`Dock8s_api_predictions_total` labelled by `predicted_class` shows you the ratio of setosa/versicolor/virginica predictions over time. If the real world has roughly equal flowers, you'd expect roughly equal predictions. A sudden spike in one class could mean a bad client is sending unusual data, or a bug in your feature pipeline.

---

## Reading the Logs

Every log line is a JSON object. Here are the most useful ones:

**Startup:**
```json
{"timestamp": "...", "level": "INFO", "message": "Starting up — loading model"}
{"timestamp": "...", "level": "INFO", "message": "Model loaded and metrics initialised"}
```

**Per-request log:**
```json
{
  "message": "{\"event\": \"request\", \"http_method\": \"POST\",
               \"http_path\": \"/predict\", \"http_status\": 200,
               \"duration_ms\": 14.2}"
}
```

**Prediction error:**
```json
{"level": "ERROR", "message": "Prediction error: ...", "exception": "..."}
```

To stream logs from all pods:
```bash
kubectl logs -l app=Dock8s-ml-api -n Dock8s-namespace -f --tail=50
```

To filter only errors:
```bash
kubectl logs -l app=Dock8s-ml-api -n Dock8s-namespace -f | grep '"level": "ERROR"'
```

---

## Understanding the Alerts

### How alerts flow

```
Prometheus evaluates rule every 15s
    → condition is true
    → alert enters PENDING state
    → condition stays true for the "for" duration
    → alert becomes FIRING
    → sent to Alertmanager
    → Alertmanager routes to Slack/PagerDuty/email
```

The `for` duration prevents flapping — a single slow request won't fire the latency alert. It must be slow for 5 continuous minutes.

### Alert severity levels

- **critical** — something is broken right now and users are affected. Page someone immediately.
- **warning** — something is degraded or trending badly. Investigate soon, not at 3am.

### Viewing active alerts

```bash
# In Prometheus UI (port 9090) → click Alerts tab
# Or query directly:
kubectl port-forward svc/kube-prometheus-kube-prome-prometheus 9090:9090 -n monitoring
# Then open http://localhost:9090/alerts
```

---

## Useful PromQL Queries

Paste these into the Prometheus UI at `http://localhost:9090`:

```promql
# Current request rate per endpoint
sum(rate(Dock8s_api_requests_total[5m])) by (endpoint)

# Error rate as a percentage
sum(rate(Dock8s_api_requests_total{http_status=~"5.."}[5m]))
/ sum(rate(Dock8s_api_requests_total[5m])) * 100

# p50 / p95 / p99 latency in milliseconds
histogram_quantile(0.50, sum(rate(Dock8s_api_request_duration_seconds_bucket[5m])) by (le)) * 1000
histogram_quantile(0.95, sum(rate(Dock8s_api_request_duration_seconds_bucket[5m])) by (le)) * 1000
histogram_quantile(0.99, sum(rate(Dock8s_api_request_duration_seconds_bucket[5m])) by (le)) * 1000

# Predictions per second by class
sum(rate(Dock8s_api_predictions_total[5m])) by (predicted_class)

# Average model confidence per class
sum(rate(Dock8s_api_prediction_confidence_sum[5m])) by (predicted_class)
/ sum(rate(Dock8s_api_prediction_confidence_count[5m])) by (predicted_class)

# Pure model inference latency p95 (milliseconds)
histogram_quantile(0.95,
  sum(rate(Dock8s_api_prediction_duration_seconds_bucket[5m])) by (le)
) * 1000

# Live requests in progress
sum(Dock8s_api_requests_in_progress) by (endpoint)

# Validation errors per second
rate(Dock8s_api_validation_errors_total[5m])

# Is the model loaded?
Dock8s_api_model_loaded
```

---

## Troubleshooting

**Grafana panels show "No data"**
```bash
# Generate traffic first
python ops/load_test.py --rps 20 --duration 30

# Check Prometheus is actually scraping the API
# Go to http://localhost:9090 → Status → Targets
# Dock8s-ml-api should show State: UP
```

**ServiceMonitor not being picked up**
```bash
# Check the label matches what Prometheus Operator expects
kubectl get servicemonitor Dock8s-ml-api-monitor -n Dock8s-namespace -o yaml | grep -A5 labels

# The release: kube-prometheus label must match your Helm release name
# If you named it differently during helm install, update the label in prometheus-config.yaml
```

**Alerts not firing even when conditions are met**
```bash
# Check PrometheusRule was applied
kubectl get prometheusrule -n Dock8s-namespace

# Check Prometheus picked it up (Status → Rules in the UI)
# Look for Dock8s_api_availability group
```

**`/metrics` endpoint returns 404**
```bash
# The image wasn't rebuilt after Phase 6 changes
eval $(minikube docker-env)
docker build -t Dock8s-ml-api:latest .
kubectl rollout restart deployment/Dock8s-ml-api -n Dock8s-namespace
```

**Helm install times out**
```bash
# Check if pods are stuck
kubectl get pods -n monitoring

# minikube may need more resources
minikube stop
minikube start --cpus=4 --memory=6g
```