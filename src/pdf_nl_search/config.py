from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    cache_mb: int
    search_limit: int
    log_level: str
    tmp_dir: str | None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load() -> Config:
    return Config(
        cache_mb=_int_env("PDFNL_CACHE_MB", 1024),
        search_limit=_int_env("PDFNL_SEARCH_LIMIT", 20_000_000),
        log_level=os.environ.get("PDFNL_LOG_LEVEL", "info"),
        tmp_dir=os.environ.get("PDFNL_TMP_DIR") or None,
    )
