"""Settings and hot-reloadable runtime config.

Two layers, deliberately separate:

* `Settings` -- secrets and deployment wiring, from the environment. Changing
  these needs a restart, which is correct: they are things like the database
  URL.
* `runtime()` -- operational knobs that a person needs to change at 11pm when
  costs spike: caps, thresholds, the budget ceiling. These live in a YAML file
  that is re-read when its mtime changes, so no deploy and no restart.

The brief requires free-tier limits to be changeable without a deploy. That is
why the split exists.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIMITS_PATH = REPO_ROOT / "config" / "limits.yaml"


class Settings(BaseSettings):
    """Deployment wiring. Read once at process start."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="SABI_", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://sabi:sabi@localhost:55432/sabi"

    # Providers. Both default to the offline deterministic implementations so
    # the whole system -- including the eval harness -- runs with no API key and
    # no network. Set these to "anthropic" / "voyage" with the matching key to
    # run for real.
    llm_provider: str = "offline"
    embedding_provider: str = "local_lsa"
    embedding_dim: int = 256

    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None

    # Admin surface. There is no default credential: if this is unset the admin
    # routes return 404, as if they did not exist.
    admin_token: str | None = None

    # Salt for hashing IP addresses. We never store a raw IP.
    ip_hash_salt: str = "dev-salt-change-me"

    limits_path: Path = DEFAULT_LIMITS_PATH
    artifact_dir: Path = REPO_ROOT / "var"

    log_json: bool = True
    environment: str = "dev"


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()


@dataclass(frozen=True)
class RuntimeConfig:
    """A snapshot of limits.yaml."""

    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    # Convenience accessors for the values read on the hot path.
    @property
    def refusal_threshold(self) -> float:
        return float(self.get("retrieval.refusal_threshold", 0.34))

    @property
    def escalation_threshold(self) -> float:
        return float(self.get("retrieval.escalation_threshold", 0.55))

    @property
    def prompt_version(self) -> str:
        return str(self.get("answering.prompt_version", "v1"))

    @property
    def monthly_ceiling_usd(self) -> float:
        return float(self.get("budget.monthly_ceiling_usd", 25.0))

    @property
    def warn_fraction(self) -> float:
        return float(self.get("budget.warn_fraction", 0.75))


_lock = threading.Lock()
_cached: tuple[float, RuntimeConfig] | None = None


def runtime(path: Path | None = None) -> RuntimeConfig:
    """Return the current runtime config, reloading if the file changed."""
    global _cached
    p = Path(path or settings().limits_path)
    try:
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        return RuntimeConfig({})

    with _lock:
        if _cached is not None and _cached[0] == mtime:
            return _cached[1]
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        cfg = RuntimeConfig(data)
        _cached = (mtime, cfg)
        return cfg


def reset_runtime_cache() -> None:
    """Test hook."""
    global _cached
    with _lock:
        _cached = None


def env_flag(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}
