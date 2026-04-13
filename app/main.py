"""
app/main.py — FastAPI inference server
Phase 6: adds Prometheus metrics, /metrics endpoint, structured JSON logging
"""

import time
import logging
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError

from app.predictor import predictor
from app.schemas import (
    PredictRequest, PredictResponse,
    BatchPredictRequest, BatchPredictResponse,
    HealthResponse,
)
from app.metrics import (
    REQUEST_COUNT, REQUEST_LATENCY, REQUESTS_IN_PROGRESS,
    PREDICTION_COUNT, PREDICTION_LATENCY, BATCH_SIZE,
    PREDICTION_CONFIDENCE, PREDICTION_ERRORS, VALIDATION_ERRORS,
    MODEL_LOADED, get_metrics_response, init_model_metrics,
)

# ── Structured JSON logger ────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines — easy to ingest into ELK/Loki."""
    def format(self, record):
        log = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
            "service":   "iris-ml-api",
            "version":   os.getenv("APP_VERSION", "1.0.0"),
            "env":       os.getenv("APP_ENV", "production"),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        return json.dumps(log)

def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

setup_logging()
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — loading model")
    try:
        predictor.load()
        init_model_metrics(predictor.metadata)
        logger.info("Model loaded and metrics initialised")
    except Exception as e:
        MODEL_LOADED.set(0)
        logger.error(f"Failed to load model: {e}")
        raise
    yield
    logger.info("Shutting down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Iris ML Inference API",
    description="Production ML inference server with Prometheus metrics",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Middleware: metrics + structured request logging ──────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    method = request.method
    path   = request.url.path

    # Skip /metrics from being tracked (avoid self-loop noise)
    if path == "/metrics":
        return await call_next(request)

    REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()
    start = time.perf_counter()

    response   = await call_next(request)
    duration   = time.perf_counter() - start
    status     = response.status_code

    REQUEST_COUNT.labels(method=method, endpoint=path, http_status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)
    REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).dec()

    logger.info(json.dumps({
        "event":       "request",
        "http_method": method,
        "http_path":   path,
        "http_status": status,
        "duration_ms": round(duration * 1000, 2),
    }))

    response.headers["X-Process-Time-Ms"] = str(round(duration * 1000, 2))
    return response


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return {"message": "Iris ML API. Docs: /docs  Metrics: /metrics"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus scrape endpoint."""
    content, media_type = get_metrics_response()
    return Response(content=content, media_type=media_type)


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
def health():
    """Kubernetes liveness probe."""
    if not predictor.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    meta = predictor.metadata
    return HealthResponse(
        status="healthy",
        model_loaded=True,
        model_type=meta["model_type"],
        num_features=meta["num_features"],
        class_names=meta["class_names"],
        test_accuracy=meta["test_accuracy"],
    )


@app.get("/ready", tags=["Operations"])
def ready():
    """Kubernetes readiness probe."""
    if not predictor.is_loaded:
        raise HTTPException(status_code=503, detail="Not ready")
    return {"status": "ready"}


@app.post("/predict", response_model=PredictResponse, tags=["Inference"])
def predict(request: PredictRequest):
    """Single prediction with full Prometheus instrumentation."""
    try:
        t0         = time.perf_counter()
        result     = predictor.predict_single(request.features)
        infer_time = time.perf_counter() - t0

        cls        = result["predicted_class"]
        confidence = max(result["probabilities"].values())

        PREDICTION_COUNT.labels(predicted_class=cls, endpoint="single").inc()
        PREDICTION_LATENCY.labels(endpoint="single").observe(infer_time)
        PREDICTION_CONFIDENCE.labels(predicted_class=cls).observe(confidence)

        return PredictResponse(**result)

    except Exception as e:
        PREDICTION_ERRORS.labels(error_type=type(e).__name__).inc()
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictResponse, tags=["Inference"])
def predict_batch(request: BatchPredictRequest):
    """Batch prediction with full Prometheus instrumentation."""
    try:
        n          = len(request.features)
        t0         = time.perf_counter()
        results    = predictor.predict_batch(request.features)
        infer_time = time.perf_counter() - t0

        BATCH_SIZE.observe(n)
        PREDICTION_LATENCY.labels(endpoint="batch").observe(infer_time)

        for r in results:
            cls        = r["predicted_class"]
            confidence = max(r["probabilities"].values())
            PREDICTION_COUNT.labels(predicted_class=cls, endpoint="batch").inc()
            PREDICTION_CONFIDENCE.labels(predicted_class=cls).observe(confidence)

        return BatchPredictResponse(
            predictions=[PredictResponse(**r) for r in results],
            total=n,
            model_version=predictor.model_version,
        )

    except Exception as e:
        PREDICTION_ERRORS.labels(error_type=type(e).__name__).inc()
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    VALIDATION_ERRORS.inc()
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )