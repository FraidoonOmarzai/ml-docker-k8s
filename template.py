import os
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')


files = [
    "train_model.py ",
    "app.py",
    "Dockerfile",
    "docker-compose.yml",
    "ml-deployment.yaml",
    "ml-config.yaml ",
    "requirements.txt",
    "setup.sh"
]

for file_ in files:
    with open(file_, "w") as f:
        logging.info(f"Creating file: {file_}")
        pass
