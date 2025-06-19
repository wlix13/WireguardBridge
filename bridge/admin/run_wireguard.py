"""WireGuard interface management script with signal handling."""

import signal
import sys
import time
from pathlib import Path

import click

from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG


class WireGuardRunner:
    """Manages WireGuard interface lifecycle with signal handling."""

    def __init__(self, interface_name: str):
        self.interface_name = interface_name
        self.running = True
        self.setup_signal_handlers()

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle termination signals."""

        LOG.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def bring_up_interface(self) -> None:
        """Bring up the WireGuard interface."""

        LOG.info(f"Bringing up WireGuard interface: {self.interface_name}")

        run_command(["wg-quick", "up", self.interface_name], sudo=True)

    def bring_down_interface(self) -> None:
        """Bring down the WireGuard interface gracefully."""

        LOG.info(f"Gracefully shutting down WireGuard interface: {self.interface_name}")

        run_command(["wg-quick", "down", self.interface_name], sudo=True)

    def monitor_interface(self) -> None:
        """Monitor the interface and wait for termination signal."""

        LOG.info("Monitoring WireGuard. Waiting for termination signal...")

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            LOG.info("Received keyboard interrupt")
            self.running = False

    def run(self) -> None:
        """Main run method - bring up interface, monitor, then clean up."""

        try:
            self.bring_up_interface()
            self.monitor_interface()
        finally:
            self.bring_down_interface()


@click.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--interface",
    "-i",
    default="wg0",
    show_default=True,
    help="WireGuard interface name",
)
@click.option(
    "--config-dir",
    default="/etc/wireguard",
    help="Directory containing WireGuard configuration files",
    type=click.Path(exists=True, path_type=Path),
)
def main(verbose: bool, interface: str, config_dir: Path) -> None:
    """Run WireGuard interface with proper signal handling."""

    config_path = Path(config_dir) / f"{interface}.conf"
    if not config_path.exists():
        LOG.error(f"WireGuard configuration not found: {config_path}")
        sys.exit(1)

    if verbose:
        LOG.info(f"Using WireGuard interface: {interface}")
        LOG.info(f"Configuration file: {config_path}")

    runner = WireGuardRunner(interface)
    try:
        runner.run()
        sys.exit(0)
    except Exception as e:
        LOG.error(f"WireGuard runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
