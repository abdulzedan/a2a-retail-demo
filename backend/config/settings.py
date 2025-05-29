"""Configuration settings for the A2A Retail Demo."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Google AI / Gemini Configuration
    google_api_key: str
    google_cloud_project: str | None = None
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = False

    # Model Configuration
    gemini_model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 2048

    # A2A Server Configuration
    inventory_agent_port: int = 8001
    customer_service_agent_port: int = 8002

    # Mesop UI Configuration
    mesop_port: int = 8000

    # Agent URLs
    inventory_agent_url: str = "http://localhost:8001"
    customer_service_agent_url: str = "http://localhost:8002"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Development Settings
    debug: bool = False
    reload: bool = True

    # Paths
    @property
    def base_dir(self) -> Path:
        """Get the base directory of the project."""
        return Path(__file__).parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Get the data directory."""
        data_dir = self.base_dir / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir

    @property
    def logs_dir(self) -> Path:
        """Get the logs directory."""
        logs_dir = self.base_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir


# Create a singleton instance
settings = Settings()
