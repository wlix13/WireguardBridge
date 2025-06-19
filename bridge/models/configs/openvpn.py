from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpenVPNConfig(BaseModel):
    """Pydantic model for OpenVPN configuration validation"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config_dir: Path = Field(
        default=Path("/etc/openvpn/config"),
        description="Directory containing OpenVPN configuration files",
    )
    log_dir: Path = Field(
        default=Path("/var/log/openvpn"),
        description="Directory for OpenVPN log files",
    )
    log_level: str | None = Field(
        default=None,
        description="OpenVPN log level (0-9)",
    )
    additional_args: str | None = Field(
        default=None,
        description="Additional OpenVPN arguments",
    )

    @field_validator("config_dir", mode="before")
    @classmethod
    def validate_config_dir(cls, v):
        """Validate that config directory exists"""

        if isinstance(v, str):
            v = Path(v)

        if not v.exists():
            raise ValueError(f"OpenVPN config directory does not exist: {v}")

        if not v.is_dir():
            raise ValueError(f"OpenVPN config path is not a directory: {v}")

        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v):
        """Validate OpenVPN log level"""

        if v is None:
            return v

        if isinstance(v, str):
            try:
                level = int(v)
            except ValueError:
                raise ValueError(f"Log level must be a number 0-9, got: {v}")
        else:
            level = v

        if not 0 <= level <= 9:
            raise ValueError(f"Log level must be between 0-9, got: {level}")

        return str(level)
