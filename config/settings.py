"""Configuration management for MAT.

Loads configuration from:
1. Environment variables (highest priority)
2. .mat-config file in project directory
3. Default values (lowest priority)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """MAT configuration settings."""

    ollama_url: str = "http://localhost:11434"
    model: str = "codellama"
    project_dir: str = field(default_factory=lambda: os.getcwd())
    verbose: bool = False
    max_retries: int = 3
    timeout: int = 120

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            ollama_url=os.environ.get("MAT_OLLAMA_URL", "http://localhost:11434"),
            model=os.environ.get("MAT_MODEL", "codellama"),
            project_dir=os.environ.get("MAT_PROJECT_DIR", os.getcwd()),
            verbose=os.environ.get("MAT_VERBOSE", "").lower() in ("1", "true", "yes"),
            max_retries=int(os.environ.get("MAT_MAX_RETRIES", "3")),
            timeout=int(os.environ.get("MAT_TIMEOUT", "120")),
        )

    @classmethod
    def from_file(cls, config_path: Path) -> Optional["Settings"]:
        """Load settings from .mat-config file.

        File format is simple key=value pairs:
            ollama_url=http://localhost:11434
            model=codellama
            project_dir=/path/to/project
        """
        if not config_path.exists():
            return None

        config_dict: dict[str, str] = {}
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config_dict[key.strip()] = value.strip()

        return cls(
            ollama_url=config_dict.get("ollama_url", "http://localhost:11434"),
            model=config_dict.get("model", "codellama"),
            project_dir=config_dict.get("project_dir", os.getcwd()),
            verbose=config_dict.get("verbose", "").lower() in ("1", "true", "yes"),
            max_retries=int(config_dict.get("max_retries", "3")),
            timeout=int(config_dict.get("timeout", "120")),
        )

    @classmethod
    def load(cls, project_dir: Optional[str] = None) -> "Settings":
        """Load settings with priority: env vars > config file > defaults.

        Args:
            project_dir: Optional project directory to look for .mat-config
        """
        # Start with defaults
        settings = cls()

        # Override with config file if it exists
        search_dir = Path(project_dir) if project_dir else Path.cwd()
        config_path = search_dir / ".mat-config"
        file_settings = cls.from_file(config_path)
        if file_settings:
            settings = file_settings

        # Override with environment variables (highest priority)
        if os.environ.get("MAT_OLLAMA_URL"):
            settings.ollama_url = os.environ["MAT_OLLAMA_URL"]
        if os.environ.get("MAT_MODEL"):
            settings.model = os.environ["MAT_MODEL"]
        if os.environ.get("MAT_PROJECT_DIR"):
            settings.project_dir = os.environ["MAT_PROJECT_DIR"]
        if os.environ.get("MAT_VERBOSE"):
            settings.verbose = os.environ["MAT_VERBOSE"].lower() in ("1", "true", "yes")
        if os.environ.get("MAT_MAX_RETRIES"):
            settings.max_retries = int(os.environ["MAT_MAX_RETRIES"])
        if os.environ.get("MAT_TIMEOUT"):
            settings.timeout = int(os.environ["MAT_TIMEOUT"])

        return settings


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance, loading if necessary."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def reload_settings(project_dir: Optional[str] = None) -> Settings:
    """Force reload of settings."""
    global _settings
    _settings = Settings.load(project_dir)
    return _settings
