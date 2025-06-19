"""Models package."""

from .configs import OpenVPNConfig, WireGuardConfig
from .processes import ProcessConfig, ProcessInfo, ProcessState


__all__ = [
    "OpenVPNConfig",
    "WireGuardConfig",
    "ProcessConfig",
    "ProcessInfo",
    "ProcessState",
]
