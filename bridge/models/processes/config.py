"""Process config."""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ProcessConfig(BaseModel):
    """Configuration for a managed process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(description="Process name")
    command: list[str] = Field(description="Command to execute")
    cwd: Path | None = Field(default=None, description="Working directory")
    env: dict[str, str] | None = Field(default=None, description="Environment variables")
    auto_restart: bool = Field(default=True, description="Enable automatic restart")
    start_retries: int = Field(default=3, ge=0, description="Number of restart attempts")
    priority: int = Field(default=100, ge=0, description="Process priority (lower = higher priority)")
    start_delay: float = Field(default=0.0, ge=0.0, description="Delay before starting process (seconds)")
    stop_timeout: float = Field(default=10.0, gt=0.0, description="Timeout for graceful stop (seconds)")
    health_check: Callable[[], bool] | None = Field(default=None, description="Health check function")
    dependencies: list[str] = Field(default_factory=list, description="list of process dependencies")
