"""
train.py - Train and save the ML model + preprocessing artifacts
"""

import os
import json
import pickle
import numpy as np
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# ── 1. Load Data ──────────────────────────────────────────────────────────────
def load_data():
    logger.info("Loading Iris dataset...")
    iris = load_iris()
    X, y = iris.data, iris.target
    feature_names = list(iris.feature_names)
    class_names   = list(iris.target_names)
    logger.info(f"Dataset shape: {X.shape} | Classes: {class_names}")
    return X, y, feature_names, class_names

# ── 2. Build Pipeline ─────────────────────────────────────────────────────────
def build_pipeline():
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42,
            n_jobs=-1
        ))
    ])

# ── 3. Train ──────────────────────────────────────────────────────────────────
def train(X_train, y_train, pipeline):
    logger.info("Training model...")
    pipeline.fit(X_train, y_train)
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring="accuracy")
    logger.info(f"CV Accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    return pipeline

# ── 4. Evaluate ───────────────────────────────────────────────────────────────
def evaluate(pipeline, X_test, y_test, class_names):
    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred, target_names=class_names, output_dict=True)
    logger.info("\n" + classification_report(y_test, y_pred, target_names=class_names))
    logger.info(f"Confusion Matrix:\n{confusion_matrix(y_test, y_pred)}")
    return report

# ── 5. Save Artifacts ─────────────────────────────────────────────────────────
def save_artifacts(pipeline, feature_names, class_names, metrics):
    # Save model pipeline (includes scaler + classifier)
    model_path = os.path.join(ARTIFACTS_DIR, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(pipeline, f)
    logger.info(f"Model saved → {model_path}")

    # Save metadata
    metadata = {
        "model_type": "RandomForestClassifier",
        "framework": "scikit-learn",
        "feature_names": feature_names,
        "class_names": class_names,
        "num_features": len(feature_names),
        "num_classes": len(class_names),
        "test_accuracy": round(metrics["accuracy"], 4),
        "pipeline_steps": ["StandardScaler", "RandomForestClassifier"]
    }
    meta_path = os.path.join(ARTIFACTS_DIR, "metadata.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved → {meta_path}")

    return model_path, meta_path

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    X, y, feature_names, class_names = load_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = build_pipeline()
    pipeline = train(X_train, y_train, pipeline)
    metrics  = evaluate(pipeline, X_test, y_test, class_names)

    model_path, meta_path = save_artifacts(pipeline, feature_names, class_names, metrics)

    logger.info("=" * 50)
    logger.info("✅ Training complete!")
    logger.info(f"   Model    → {model_path}")
    logger.info(f"   Metadata → {meta_path}")
    logger.info(f"   Test Accuracy: {metrics['accuracy']:.4f}")

if __name__ == "__main__":
    main()