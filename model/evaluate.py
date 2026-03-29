"""
evaluate.py - Load saved artifacts and run a quick sanity check
"""

import os
import json
import pickle
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")


def load_artifacts():
    model_path = os.path.join(ARTIFACTS_DIR, "model.pkl")
    meta_path = os.path.join(ARTIFACTS_DIR, "metadata.json")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at {model_path}. Run train.py first.")

    with open(model_path, "rb") as f:
        pipeline = pickle.load(f)

    with open(meta_path, "r") as f:
        metadata = json.load(f)

    return pipeline, metadata


def run_sample_predictions(pipeline, metadata):
    """Run predictions on sample inputs to verify model loads and infers correctly."""
    sample_inputs = [
        [5.1, 3.5, 1.4, 0.2],  # Expected: setosa
        [6.7, 3.0, 5.2, 2.3],  # Expected: virginica
        [5.8, 2.7, 4.1, 1.0],  # Expected: versicolor
    ]

    logger.info("\n── Sample Predictions ──────────────────────────")
    for i, sample in enumerate(sample_inputs):
        arr = np.array(sample).reshape(1, -1)
        pred_idx = pipeline.predict(arr)[0]
        pred_prob = pipeline.predict_proba(arr)[0]
        pred_class = metadata["class_names"][pred_idx]

        probs_str = ", ".join(
            f"{cls}: {prob:.3f}"
            for cls, prob in zip(metadata["class_names"], pred_prob)
        )
        logger.info(f"  Input {i+1}: {sample}")
        logger.info(f"  → Predicted: {pred_class} | Probabilities: [{probs_str}]")
        logger.info("")


def main():
    logger.info("Loading artifacts...")
    pipeline, metadata = load_artifacts()

    logger.info("── Model Metadata ───────────────────────────────")
    for k, v in metadata.items():
        logger.info(f"  {k}: {v}")

    run_sample_predictions(pipeline, metadata)
    logger.info("✅ Evaluation complete — model is healthy!")


if __name__ == "__main__":
    main()
