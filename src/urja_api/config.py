import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Portal Upstream
    portal_base_url: str = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech").rstrip("/")
    portal_username: str = os.getenv("URJA_PORTAL_USERNAME", "")
    portal_password: str = os.getenv("URJA_PORTAL_PASSWORD", "")
    portal_user_agent: str = os.getenv(
        "PORTAL_USER_AGENT",
        "UrjaMeterOpsApi/1.0 (take-home candidate; https://github.com/<GITHUB_USERNAME>/<REPO_NAME>)",
    )

    # Polite Client & Resilience
    max_concurrency: int = int(os.getenv("PORTAL_MAX_CONCURRENCY", "2"))
    request_delay_sec: float = float(os.getenv("PORTAL_REQUEST_DELAY_SEC", "0.2"))
    timeout_sec: float = float(os.getenv("PORTAL_TIMEOUT_SEC", "15.0"))
    max_retries: int = int(os.getenv("PORTAL_MAX_RETRIES", "3"))

    # Service Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    environment: str = os.getenv("ENVIRONMENT", "development")

    # Local Storage
    database_path: str = os.getenv("DATABASE_PATH", "urja_local.db")

    # Cache TTLs (seconds)
    # Metadata/Hierarchy: 1 hour (3600s), Consumption: 15 min (900s), SWR: 24h (86400s)
    cache_ttl_meters_sec: int = int(os.getenv("CACHE_TTL_METERS_SEC", "3600"))
    cache_ttl_consumption_sec: int = int(os.getenv("CACHE_TTL_CONSUMPTION_SEC", "900"))
    cache_swr_window_sec: int = int(os.getenv("CACHE_SWR_WINDOW_SEC", "86400"))
    sync_cooldown_sec: int = int(os.getenv("SYNC_COOLDOWN_SEC", "60"))

    # Testing
    enable_live_portal_tests: bool = os.getenv("ENABLE_LIVE_PORTAL_TESTS", "false").lower() in ("true", "1", "yes")

    def __repr__(self) -> str:
        # Never leak password or credentials in string representation
        return (
            f"Settings(portal_base_url='{self.portal_base_url}', "
            f"portal_username='{'***' if self.portal_username else ''}', "
            f"max_concurrency={self.max_concurrency}, timeout_sec={self.timeout_sec}, "
            f"database_path='{self.database_path}')"
        )


settings = Settings()
