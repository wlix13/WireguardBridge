"""Admin module for WireGuard Bridge."""

from .setup_openvpn import OpenVPNSetup
from .setup_wireguard import WireGuardSetup


__all__ = [
    "OpenVPNSetup",
    "WireGuardSetup",
]
