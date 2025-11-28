import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    
    APP_NAME: str = os.getenv("APP_NAME", "UnisonMap")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    VALID_DOMAIN: str = os.getenv("VALID_DOMAIN", "@unison.mx")
    
    ORS_API_KEY: str = os.getenv("ORS_API_KEY")
    ORS_BASE_URL: str = os.getenv("ORS_BASE_URL", "https://api.openrouteservice.org/v2/directions/foot-walking")
    ORS_TIMEOUT: float = float(os.getenv("ORS_TIMEOUT", 10))
    ORS_MAX_RETRIES: int = int(os.getenv("ORS_MAX_RETRIES", 2))
    ORS_BACKOFF_FACTOR: float = float(os.getenv("ORS_BACKOFF_FACTOR", 0.75))

    ORS_ALLOWED_PROFILES: List[str] = [
        profile.strip().lower()
        for profile in os.getenv(
            "ORS_ALLOWED_PROFILES",
            "foot-walking,driving-car,cycling-regular",
        ).split(",")
        if profile.strip()
    ]

    REDIS_URL: str | None = os.getenv("REDIS_URL")
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", 10800))  # 3 horas
    CACHE_MAX_TTL_SECONDS: int = int(os.getenv("CACHE_MAX_TTL_SECONDS", 21600))  # 6 horas
    CACHE_SQLITE_PATH: str = os.getenv("CACHE_SQLITE_PATH", str(BASE_DIR / "cache.sqlite"))
    CACHE_LOCK_TIMEOUT_SECONDS: int = int(os.getenv("CACHE_LOCK_TIMEOUT_SECONDS", 30))
    CACHE_ALLOW_HEADER_OVERRIDE: bool = os.getenv("CACHE_ALLOW_HEADER_OVERRIDE", "False").lower() == "true"
    CACHE_ALWAYS_COMPRESS: bool = os.getenv("CACHE_ALWAYS_COMPRESS", "True").lower() == "true"

settings = Settings()