"""OpenVPN process wrapper for WireGuard Bridge."""

import os
from pathlib import Path

from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG
from bridge.models import ProcessConfig


class OpenVPNProcess:
    """OpenVPN process wrapper with health checking and configuration."""

    def __init__(
        self,
        config_path: Path,
        log_level: str | None = None,
        additional_args: str | None = None,
        log_dir: Path = Path("/var/log/openvpn"),
    ):
        self.config_path = config_path
        self.log_level = log_level
        self.additional_args = additional_args
        self.log_dir = log_dir
        self.log_file = self.log_dir / "openvpn.log"

    def get_process_config(self) -> ProcessConfig:
        """Get ProcessConfig for OpenVPN."""

        self.log_dir.mkdir(parents=True, exist_ok=True)

        command = ["sudo", "openvpn", "--config", str(self.config_path)]

        command.extend(["--log", str(self.log_file)])

        if self.log_level:
            command.extend(["--verb", self.log_level])

        if self.additional_args:
            command.extend(self.additional_args.split())

        command.extend(["--user", "bridge", "--group", "bridge"])

        env = os.environ.copy()

        return ProcessConfig(
            name="openvpn",
            command=command,
            env=env,
            auto_restart=True,
            start_retries=3,
            priority=100,  # Higher priority than WireGuard
            stop_timeout=10.0,
            health_check=self.health_check,
            dependencies=[],  # Base process
        )

    def health_check(self) -> bool:
        """Check if OpenVPN tunnel is healthy."""

        try:
            result = run_command(["ip", "addr", "show", "type", "tun"])

            if result.returncode == 0 and "tun" in result.stdout:
                return True

            LOG.warning("OpenVPN health check: No tun interface found")
            return False

        except Exception as e:
            LOG.warning(f"OpenVPN health check failed: {e}")
            return False

    def get_tunnel_interface(self) -> str | None:
        """Get the name of the OpenVPN tunnel interface."""

        try:
            result = run_command(["ip", "addr", "show", "type", "tun"])

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "tun" in line and ":" in line:
                        interface = line.split(":")[1].strip().split("@")[0]
                        if "tun" in interface:
                            return interface

        except Exception as e:
            LOG.error(f"Failed to get tunnel interface: {e}")

        return None
