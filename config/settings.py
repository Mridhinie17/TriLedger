from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "TriLedger"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Directories
    BASE_DIR: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / "data"
    CONFIG_DIR: Path = PROJECT_ROOT / "config"
    EVAL_DIR: Path = PROJECT_ROOT / "eval"
    PDF_DIR: Path = PROJECT_ROOT / "data" / "invoices_pdf"

    # Database
    # Default is SQLite for zero-dependency local runs; easily switchable to DuckDB or PostgreSQL
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT}/data/triledger.db"

    # Groq / LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Currencies
    BASE_CURRENCY: str = "INR"
    SUPPORTED_CURRENCIES: list[str] = ["INR", "USD", "EUR", "JPY"]

    # Tolerances file
    TOLERANCES_FILE: Path = PROJECT_ROOT / "config" / "tolerances.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def load_tolerances(self) -> dict[str, Any]:
        if not self.TOLERANCES_FILE.exists():
            return {}
        with open(self.TOLERANCES_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


settings = Settings()
