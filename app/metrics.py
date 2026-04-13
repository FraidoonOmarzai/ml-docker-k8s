"""
app/metrics.py
Defines all Prometheus metrics for the ML inference API.
Uses prometheus_client — add to requirements-serve.txt.
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# ── Request metrics ───────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    name="iris_api_requests_total",
    documentation="Total HTTP requests received",
    labelnames=["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    name="iris_api_request_duration_seconds",
    documentation="HTTP request latency in seconds",
    labelnames=["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

REQUESTS_IN_PROGRESS = Gauge(
    name="iris_api_requests_in_progress",
    documentation="Number of HTTP requests currently being processed",
    labelnames=["method", "endpoint"],
)

# ── Inference metrics ─────────────────────────────────────────────────────────

PREDICTION_COUNT = Counter(
    name="iris_api_predictions_total",
    documentation="Total predictions served",
    labelnames=["predicted_class", "endpoint"],  # endpoint: single vs batch
)

PREDICTION_LATENCY = Histogram(
    name="iris_api_prediction_duration_seconds",
    documentation="Time spent purely on model inference (excludes HTTP overhead)",
    labelnames=["endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25],
)

BATCH_SIZE = Histogram(
    name="iris_api_batch_size",
    documentation="Number of samples per batch prediction request",
    buckets=[1, 2, 5, 10, 20, 50, 100],
)

PREDICTION_CONFIDENCE = Histogram(
    name="iris_api_prediction_confidence",
    documentation="Model confidence (max probability) per prediction",
    labelnames=["predicted_class"],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0],
)

# ── Error metrics ─────────────────────────────────────────────────────────────

PREDICTION_ERRORS = Counter(
    name="iris_api_prediction_errors_total",
    documentation="Total prediction errors",
    labelnames=["error_type"],
)

VALIDATION_ERRORS = Counter(
    name="iris_api_validation_errors_total",
    documentation="Total input validation failures (422 responses)",
)

# ── Model / system metrics ────────────────────────────────────────────────────

MODEL_INFO = Info(
    name="iris_api_model",
    documentation="Static metadata about the loaded model",
)

MODEL_LOADED = Gauge(
    name="iris_api_model_loaded",
    documentation="1 if the model is loaded and ready, 0 otherwise",
)

# ── Helper: expose metrics endpoint ──────────────────────────────────────────


def get_metrics_response():
    """Returns (content, media_type) tuple for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def init_model_metrics(metadata: dict):
    """Call once after model loads to set static labels and mark as ready."""
    MODEL_INFO.info(
        {
            "model_type": metadata.get("model_type", "unknown"),
            "framework": metadata.get("framework", "scikit-learn"),
            "num_features": str(metadata.get("num_features", 0)),
            "num_classes": str(metadata.get("num_classes", 0)),
            "test_accuracy": str(metadata.get("test_accuracy", 0.0)),
            "version": "1.0.0",
        }
    )
    MODEL_LOADED.set(1)
