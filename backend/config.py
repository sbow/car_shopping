"""Loads config.toml and environment variables."""

import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

_CONFIG_PATH = Path(__file__).parents[1] / "config.toml"


def load() -> dict:
    with open(_CONFIG_PATH, "rb") as f:
        cfg = tomllib.load(f)
    cfg["database_url"] = os.environ["DATABASE_URL"]
    cfg["twilio"] = {
        "account_sid": os.environ["TWILIO_ACCOUNT_SID"],
        "auth_token": os.environ["TWILIO_AUTH_TOKEN"],
        "from_number": os.environ["TWILIO_FROM_NUMBER"],
    }
    return cfg
