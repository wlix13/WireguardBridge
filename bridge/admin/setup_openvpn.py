"""OpenVPN client setup script for WireGuard Bridge."""

from pathlib import Path

import click

from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG
from bridge.models.configs import OpenVPNConfig


class OpenVPNSetup:
    """OpenVPN setup and configuration management"""

    def __init__(self, config: OpenVPNConfig):
        """Initialize OpenVPN setup with configuration"""

        self.config = config

    @classmethod
    def from_config(cls, config: OpenVPNConfig) -> "OpenVPNSetup":
        """Create OpenVPNSetup from pydantic config"""

        instance = cls(config)

        instance.config.log_dir.mkdir(parents=True, exist_ok=True)

        LOG.debug(f"Using OpenVPN config directory: {config.config_dir}")
        LOG.debug(f"Log directory: {config.log_dir}")

        return instance

    @classmethod
    def from_click_options(
        cls,
        config_dir: Path,
        log_level: str | None = None,
        additional_args: str | None = None,
    ) -> "OpenVPNSetup":
        """Create OpenVPNSetup from Click options"""

        config = OpenVPNConfig(
            config_dir=config_dir,
            log_level=log_level,
            additional_args=additional_args,
        )
        return cls.from_config(config)

    def find_openvpn_config(self) -> Path:
        """Find OpenVPN configuration file."""

        for pattern in ["*.ovpn", "*.conf"]:
            for config_file in self.config.config_dir.glob(pattern):
                if config_file.is_file():
                    LOG.info(f"Found OpenVPN config: {config_file}")
                    return config_file

        raise click.ClickException(f"No OpenVPN configuration (.ovpn or .conf) found in {self.config.config_dir}")

    @staticmethod
    def enable_ip_forwarding() -> None:
        """Enable IP forwarding for routing."""

        LOG.debug("Enabling IP forwarding...")

        forwarding_settings = [
            ("net.ipv4.ip_forward", 1),
            ("net.ipv4.conf.all.forwarding", 1),
            ("net.ipv6.conf.all.forwarding", 1),
        ]

        for setting, value in forwarding_settings:
            try:
                run_command(["sysctl", "-w", f"{setting}={value}"], sudo=True)
            except Exception as e:
                LOG.error(f"Failed to set {setting}={value}: {e}")
                raise

    def setup(self) -> Path:
        """Main setup method"""

        try:
            openvpn_config = self.find_openvpn_config()

            self.enable_ip_forwarding()

            return openvpn_config

        except Exception as e:
            LOG.error(f"OpenVPN setup failed: {e}")
            raise e


@click.command()
@click.option(
    "--config-dir",
    default="/etc/openvpn/config",
    help="Directory containing OpenVPN configuration files",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--log-level",
    help="OpenVPN log level (0-9)",
    type=str,
)
@click.option(
    "--additional-args",
    help="Additional OpenVPN command line arguments",
    type=str,
)
def main(
    config_dir: Path,
    log_level: str | None,
    additional_args: str | None,
) -> None:
    """Set up OpenVPN client configuration."""

    openvpn_setup = OpenVPNSetup.from_click_options(
        config_dir=config_dir,
        log_level=log_level,
        additional_args=additional_args,
    )

    openvpn_setup.setup()


if __name__ == "__main__":
    main()
