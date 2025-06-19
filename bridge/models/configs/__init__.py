"""Configs models."""

from .openvpn import OpenVPNConfig
from .wireguard import WireGuardConfig


__all__ = [
    "OpenVPNConfig",
    "WireGuardConfig",
]
