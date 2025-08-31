# train_model.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.datasets import make_classification
import joblib
import os


class Training:
    def __init__(self):
        pass

    def create_sample_data(self):
        """Create sample classification dataset"""
        print("Creating sample dataset...")
        X, y = make_classification(
            n_samples=1000,
            n_features=20,
            n_informative=15,
            n_redundant=5,
            n_classes=3,
            random_state=42
        )

        # Create feature names
        feature_names = [f'feature_{i}' for i in range(X.shape[1])]

        # Convert to DataFrame
        df = pd.DataFrame(X, columns=feature_names)
        df['target'] = y

        return df

    def train_model(self):
        """Train and save the machine learning model"""
        # Create sample data
        df = self.create_sample_data()

        # Prepare features and target
        X = df.drop('target', axis=1)
        y = df['target']

        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        print(f"Training set size: {X_train.shape[0]}")
        print(f"Test set size: {X_test.shape[0]}")

        # Train Random Forest model
        print("Training Random Forest model...")
        model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10
        )

        model.fit(X_train, y_train)

        # Make predictions
        y_pred = model.predict(X_test)

        # Evaluate model
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred))

        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)

        # Save the model
        model_path = 'models/rf_classifier.pkl'
        joblib.dump(model, model_path)
        print(f"Model saved to {model_path}")

        # Save feature names for later use
        feature_names = X.columns.tolist()
        joblib.dump(feature_names, 'models/feature_names.pkl')
        print("Feature names saved")

        return accuracy


if __name__ == "__main__":
    trainer = Training()
    accuracy = trainer.train_model()
    print(f"Training completed with accuracy: {accuracy:.4f}")
