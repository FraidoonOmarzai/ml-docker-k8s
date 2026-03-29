"""
main.py - FastAPI inference server
"""

import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.predictor import predictors
from app.schemas import (
    PredictRequest,
    PredictResponse,
    BatchPredictRequest,
    BatchPredictResponse,
    HealthResponse,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: load model on startup ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting up — loading model...")
    try:
        predictors.load()
        logger.info("✅ Model ready. Server accepting requests.")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        raise
    yield
    logger.info("Shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Docker + k8s Inference API",
    description="Docker and k8s deployment example with FastAPI, using an Iris ML model.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Middleware: request timing ────────────────────────────────────────────────
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)"
    )
    return response


# ── Routes ────────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
def root():
    return {"message": "API is running. Visit /docs for the Swagger UI."}


@app.get("/health", response_model=HealthResponse, tags=["Operations"])
def health():
    """Kubernetes liveness + readiness probe endpoint."""
    if not predictors.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    meta = predictors.metadata
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
    """Readiness check — returns 200 only when model is loaded."""
    if not predictors.is_loaded:
        raise HTTPException(status_code=503, detail="Not ready")
    return {"status": "ready"}


@app.post("/predict", response_model=PredictResponse, tags=["Inference"])
def predict(request: PredictRequest):
    """
    Single prediction endpoint.

    Send 4 Iris features:
    - sepal length (cm)
    - sepal width (cm)
    - petal length (cm)
    - petal width (cm)
    """
    try:
        result = predictors.predict_single(request.features)
        return PredictResponse(**result)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictResponse, tags=["Inference"])
def predict_batch(request: BatchPredictRequest):
    """
    Batch prediction endpoint — up to 100 samples per request.
    """
    try:
        results = predictors.predict_batch(request.features)
        return BatchPredictResponse(
            predictions=[PredictResponse(**r) for r in results],
            total=len(results),
            model_version=predictors.model_version,
        )
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )
