"""WireGuard process wrapper for WireGuard Bridge."""

import os
from pathlib import Path

from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG
from bridge.models import ProcessConfig


class WireGuardProcess:
    """WireGuard process wrapper with health checking and configuration."""

    def __init__(
        self,
        interface_name: str = "wg0",
        config_dir: Path = Path("/etc/wireguard"),
    ):
        self.interface_name = interface_name
        self.config_dir = config_dir

    def get_process_config(self) -> ProcessConfig:
        """Get ProcessConfig for WireGuard."""

        command = [
            "run-wireguard",
            "--interface",
            self.interface_name,
            "--config-dir",
            str(self.config_dir),
            "--verbose",
        ]

        env = os.environ.copy()

        return ProcessConfig(
            name="wireguard",
            command=command,
            env=env,
            auto_restart=True,
            start_retries=3,
            priority=200,  # Lower priority than OpenVPN
            stop_timeout=15.0,  # Allow more time for interface cleanup
            health_check=self.health_check,
            dependencies=["openvpn"],
        )

    def health_check(self) -> bool:
        """Check if WireGuard interface is healthy."""

        try:
            result = run_command(["ip", "addr", "show", self.interface_name])

            if result.returncode == 0:
                if "state UP" in result.stdout or "UP" in result.stdout:
                    return True
                else:
                    LOG.warning(f"WireGuard interface {self.interface_name} is DOWN")
                    return False
            else:
                LOG.warning(f"WireGuard interface {self.interface_name} not found")
                return False

        except Exception as e:
            LOG.warning(f"WireGuard health check failed: {e}")
            return False

    def is_interface_up(self) -> bool:
        """Check if WireGuard interface is up."""

        try:
            result = run_command(["wg", "show", self.interface_name])
            return result.returncode == 0
        except Exception:
            return False

    def get_interface_stats(self) -> dict[str, str] | None:
        """Get WireGuard interface statistics."""

        try:
            result = run_command(["wg", "show", self.interface_name])

            if result.returncode == 0:
                stats = {}
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("listening port:"):
                        stats["port"] = line.split(":", 1)[1].strip()
                    elif line.startswith("peer:"):
                        if "peers" not in stats:
                            stats["peers"] = []
                        stats["peers"].append(line.split(":", 1)[1].strip())
                return stats

        except Exception as e:
            LOG.error(f"Failed to get WireGuard stats: {e}")

        return None

    def wait_for_dependency(self, timeout: int = 30) -> bool:
        """Wait for OpenVPN tunnel interface to be available."""

        LOG.info("Waiting for OpenVPN tunnel interface...")

        for i in range(timeout):
            try:
                result = run_command(["ip", "addr", "show", "type", "tun"])

                if result.returncode == 0 and "tun" in result.stdout:
                    for line in result.stdout.split("\n"):
                        if "tun" in line and ":" in line:
                            tun_name = line.split(":")[1].strip().split("@")[0]
                            if "tun" in tun_name:
                                return True

                if i % 5 == 0:
                    LOG.info(f"Still waiting for tun interface... ({i}/{timeout})")

            except Exception as e:
                LOG.warning(f"Error checking for tun interface: {e}")

            if i < timeout - 1:
                import time

                time.sleep(1)

        LOG.error("OpenVPN tunnel interface not found after timeout")
        return False
