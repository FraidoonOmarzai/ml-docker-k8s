import os
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s]: %(message)s:")

dirs = [
    os.path.join("model", "artifacts"),
    "app"
]

for dir_ in dirs:
    os.makedirs(dir_, exist_ok=True)
    # To get Git to recognize an empty directory, the unwritten rule is to put a file named .gitkeep in it
    with open(os.path.join(dir_, ".gitkeep"), "w") as f:
        logging.info(f"Creating directory:{dir_}")
        pass


files = [
    os.path.join("model", "__init__.py"),
    os.path.join("model", "train.py"),
    os.path.join("model", "evaluate.py"),
    os.path.join("app", "main.py"),
    os.path.join("app", "predictor.py"),
    os.path.join("app", "schemas.py"),
    "Dockerfile",
    "requirements-train.txt",
    "requirements-serve.txt"
]

for file_ in files:
    with open(file_, "w") as f:
        logging.info(f"Creating file: {file_}")
        pass