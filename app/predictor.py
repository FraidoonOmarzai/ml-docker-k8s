"""
predictor.py - Handles model loading, caching, and inference
"""

import os
import json
import pickle
import numpy as np
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Resolve artifact paths relative to this file or from env override
ARTIFACTS_DIR = os.getenv(
    "ARTIFACTS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "model", "artifacts")
)


class ModelPredictor:
    """
    Singleton-style predictor that loads the model once at startup
    and serves predictions efficiently.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.pipeline = None
        self.metadata = None
        self._initialized = True

    def load(self) -> None:
        """Load model pipeline and metadata from disk."""
        model_path = os.path.join(ARTIFACTS_DIR, "model.pkl")
        meta_path  = os.path.join(ARTIFACTS_DIR, "metadata.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model artifact not found at: {model_path}\n"
                "Run model/train.py first to generate artifacts."
            )

        logger.info(f"Loading model from {model_path}...")
        with open(model_path, "rb") as f:
            self.pipeline = pickle.load(f)

        with open(meta_path, "r") as f:
            self.metadata = json.load(f)

        logger.info(
            f"Model loaded ✅ | Type: {self.metadata['model_type']} | "
            f"Accuracy: {self.metadata['test_accuracy']}"
        )

    @property
    def is_loaded(self) -> bool:
        return self.pipeline is not None and self.metadata is not None

    @property
    def class_names(self) -> List[str]:
        return self.metadata["class_names"]

    @property
    def model_version(self) -> str:
        return f"{self.metadata['model_type']}_v1"

    def predict_single(self, features: List[float]) -> Dict:
        """Run inference on a single feature vector."""
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")

        arr = np.array(features, dtype=np.float64).reshape(1, -1)
        pred_idx  = int(self.pipeline.predict(arr)[0])
        pred_prob = self.pipeline.predict_proba(arr)[0].tolist()

        return {
            "predicted_class": self.class_names[pred_idx],
            "predicted_index": pred_idx,
            "probabilities": {
                cls: round(prob, 6)
                for cls, prob in zip(self.class_names, pred_prob)
            },
            "model_version": self.model_version,
        }

    def predict_batch(self, features_list: List[List[float]]) -> List[Dict]:
        """Run inference on a batch of feature vectors."""
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")

        arr = np.array(features_list, dtype=np.float64)
        pred_idxs  = self.pipeline.predict(arr).tolist()
        pred_probs = self.pipeline.predict_proba(arr).tolist()

        results = []
        for idx, probs in zip(pred_idxs, pred_probs):
            results.append({
                "predicted_class": self.class_names[idx],
                "predicted_index": int(idx),
                "probabilities": {
                    cls: round(prob, 6)
                    for cls, prob in zip(self.class_names, probs)
                },
                "model_version": self.model_version,
            })
        return results


# Module-level singleton
predictors = ModelPredictor()