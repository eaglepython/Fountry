import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,*",
    ).split(",")
    CACHE_DIR: str = os.getenv("CACHE_DIR", "./cache")
    CACHE_TTL_HOURS: int = int(os.getenv("CACHE_TTL_HOURS", "24"))
    POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")


settings = Settings()
