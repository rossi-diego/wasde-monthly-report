from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env file at project root
load_dotenv()

# Project folders
PROJECT_FOLDER = Path(__file__).resolve().parents[1]
DATA_FOLDER = PROJECT_FOLDER / "data"

# Data files
RAW_DATA = DATA_FOLDER / "raw_data"
PROCESSED_DATA = DATA_FOLDER / "processed_data"
WASDE_FOLDER = DATA_FOLDER / "wasde_files"

# WASDE Token (used for Cornell USDA API access)
WASDE_JWT = os.getenv("WASDE_JWT")

# Optional: raise an error if token is missing
if WASDE_JWT is None:
    raise EnvironmentError("Missing WASDE_JWT in your .env file")
