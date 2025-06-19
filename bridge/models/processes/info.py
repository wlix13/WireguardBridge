"""Process info."""

import asyncio
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .config import ProcessConfig


class ProcessState(Enum):
    """Process state enumeration."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"
    BACKOFF = "backoff"


class ProcessInfo(BaseModel):
    """Runtime information about a managed process."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: ProcessConfig = Field(description="Process configuration")
    state: ProcessState = Field(default=ProcessState.STOPPED, description="Current process state")
    process: asyncio.subprocess.Process | None = Field(default=None, description="Subprocess object")
    start_time: float | None = Field(default=None, description="Process start timestamp")
    restart_count: int = Field(default=0, ge=0, description="Number of restarts")
    last_restart: float | None = Field(default=None, description="Last restart timestamp")
    pid: int | None = Field(default=None, description="Process ID")
