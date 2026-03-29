"""
schemas.py - Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, List


# ── Shared Base Model ─────────────────────────────────────────────────────────


class APIModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


# ── Requests ──────────────────────────────────────────────────────────────────


class PredictRequest(APIModel):
    """Single prediction request."""

    features: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="4 Iris features: sepal_length, sepal_width, petal_length, petal_width (cm)",
        examples=[[5.1, 3.5, 1.4, 0.2]],
    )

    @field_validator("features")
    @classmethod
    def features_must_be_positive(cls, v):
        if any(f <= 0 for f in v):
            raise ValueError("All feature values must be positive numbers")
        return v


class BatchPredictRequest(APIModel):
    """Batch prediction request — up to 100 samples."""

    features: List[List[float]] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of feature vectors, each with 4 values",
    )

    @field_validator("features")
    @classmethod
    def validate_each_row(cls, v):
        for i, row in enumerate(v):
            if len(row) != 4:
                raise ValueError(
                    f"Row {i} must have exactly 4 features, got {len(row)}"
                )
            if any(f <= 0 for f in row):
                raise ValueError(f"Row {i} contains non-positive values")
        return v


# ── Responses ─────────────────────────────────────────────────────────────────


class PredictResponse(APIModel):
    """Single prediction response."""

    predicted_class: str
    predicted_index: int
    probabilities: Dict[str, float]
    model_version: str


class BatchPredictResponse(APIModel):
    """Batch prediction response."""

    predictions: List[PredictResponse]
    total: int
    model_version: str


class HealthResponse(APIModel):
    status: str
    model_loaded: bool
    model_type: str
    num_features: int
    class_names: List[str]
    test_accuracy: float
