"""Main orchestrator for WireGuard Bridge."""

import asyncio
import json
import os
import sys
import time
from ipaddress import IPv4Network
from pathlib import Path

import click

from bridge.admin import OpenVPNSetup, WireGuardSetup
from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG
from bridge.models import OpenVPNConfig
from bridge.models.processes import ProcessState
from bridge.processes import OpenVPNProcess, ProcessManager, WireGuardProcess


class WireGuardBridgeOrchestrator:
    """Main orchestrator."""

    def __init__(self, config_name: str = "wg0"):
        self.config_name = config_name
        self.process_manager = ProcessManager()

        self.openvpn_config_dir = Path("/etc/openvpn/config")
        self.wireguard_config_dir = Path("/etc/wireguard")

    async def setup_phase_1_openvpn(self) -> None:
        """Phase 1: Set up OpenVPN configuration."""

        LOG.info("Phase 1: Setting up OpenVPN...")

        try:
            log_level = os.environ.get("OPENVPN_LOG_LEVEL")
            additional_args = os.environ.get("OPENVPN_ADDITIONAL_ARGS")

            self.openvpn_config = OpenVPNConfig(
                config_dir=self.openvpn_config_dir,
                log_level=log_level,
                additional_args=additional_args,
            )

            openvpn_setup = OpenVPNSetup.from_config(self.openvpn_config)
            self.openvpn_config_path = openvpn_setup.setup()

            LOG.success("Phase 1 completed")

        except Exception as e:
            LOG.error(f"OpenVPN setup failed: {e}")
            raise

    async def setup_phase_2_start_openvpn_process(self) -> None:
        """Phase 2: Add OpenVPN process to manager and start it."""

        LOG.info("Phase 2: Starting OpenVPN process...")

        try:
            if not self.openvpn_config or not self.openvpn_config_path:
                raise RuntimeError("OpenVPN not configured in Phase 1")

            openvpn_process = OpenVPNProcess(
                config_path=self.openvpn_config_path,
                log_level=self.openvpn_config.log_level,
                additional_args=self.openvpn_config.additional_args,
                log_dir=self.openvpn_config.log_dir,
            )
            await self.process_manager.add_process(openvpn_process.get_process_config())

            if not await self.process_manager.start_process("openvpn"):
                raise RuntimeError("Failed to start OpenVPN process")

            await self._wait_for_openvpn_tunnel()

            LOG.success("Phase 2 completed")

        except Exception as e:
            LOG.error(f"OpenVPN process setup failed: {e}")
            raise

    async def _wait_for_openvpn_tunnel(self, timeout: int = 60) -> None:
        """Wait for OpenVPN tunnel to be established."""

        LOG.info("Waiting for OpenVPN tunnel to be established...")

        openvpn_process_info = self.process_manager.processes.get("openvpn")
        if not openvpn_process_info:
            raise RuntimeError("OpenVPN process not found in manager")

        health_check_func = openvpn_process_info.config.health_check
        if not health_check_func:
            LOG.warning("OpenVPN process has no health check. Assuming it's healthy.")
            return

        for i in range(timeout):
            openvpn_status = self.process_manager.get_process_status("openvpn")
            if not openvpn_status or openvpn_status["state"] != "running":
                raise RuntimeError("OpenVPN process stopped unexpectedly")

            try:
                if health_check_func():
                    LOG.info("OpenVPN tunnel established")
                    return

            except Exception as e:
                LOG.warning(f"Error checking tunnel: {e}")

            if i % 10 == 0:
                LOG.warning(f"Still waiting for tunnel... ({i}/{timeout})")

            await asyncio.sleep(1)

        raise RuntimeError("OpenVPN tunnel not established within timeout")

    async def setup_phase_3_wireguard(self) -> None:
        """Phase 3: Set up WireGuard configuration."""

        LOG.info("Phase 3: Setting up WireGuard...")

        try:
            wireguard_setup = WireGuardSetup.from_click_options(
                wg_port=int(os.environ.get("WG_PORT", "1195")),
                config_name=self.config_name,
                public_ip=None,  # Will be auto-detected
                address_range=IPv4Network(os.environ.get("WG_ADDRESS_RANGE", "10.9.0.0/24")),
                clients=os.environ.get("WG_CLIENTS", "client").split(","),
            )

            wireguard_setup.setup()

            LOG.success("Phase 3 completed")

        except Exception as e:
            LOG.error(f"WireGuard setup failed: {e}")
            raise

    async def setup_phase_4_add_wireguard_process(self) -> None:
        """Phase 4: Add WireGuard process to manager."""

        LOG.info("Phase 4: Adding WireGuard process to manager...")

        try:
            wireguard_process = WireGuardProcess(interface_name=self.config_name, config_dir=self.wireguard_config_dir)
            await self.process_manager.add_process(wireguard_process.get_process_config())

        except Exception as e:
            LOG.error(f"WireGuard process setup failed: {e}")
            raise

    async def health_check_endpoint(self) -> bool:
        """Health check endpoint for container monitoring."""

        status_file = self.process_manager.status_file

        try:
            if not status_file.exists():
                LOG.error("Health check failed: Status file not found.")
                return False

            if time.time() - status_file.stat().st_mtime > 15:
                LOG.error("Health check failed: Status file is stale.")
                return False

            with open(status_file) as f:
                statuses = json.load(f)

            openvpn_status = statuses.get("openvpn")
            wireguard_status = statuses.get("wireguard")

            openvpn_healthy = openvpn_status and openvpn_status["state"] == ProcessState.RUNNING.value
            wireguard_healthy = wireguard_status and wireguard_status["state"] == ProcessState.RUNNING.value

            if not openvpn_healthy:
                LOG.error(f"OpenVPN process not healthy: {openvpn_status}")
                return False

            if not wireguard_healthy:
                LOG.error(f"WireGuard process not healthy: {wireguard_status}")
                return False

            return openvpn_healthy and wireguard_healthy

        except Exception as e:
            LOG.error(f"Health check failed: {e}")
            return False

    async def run(self) -> None:
        """Main run method - orchestrate the entire bridge setup and process management."""

        try:
            LOG.info("Starting WireGuard Bridge...")

            self.openvpn_config_dir.parent.mkdir(parents=True, exist_ok=True)
            self.wireguard_config_dir.mkdir(parents=True, exist_ok=True)

            LOG.info("Ensuring correct directory permissions...")
            user = os.environ.get("USER", "bridge")
            try:
                run_command(["chown", f"{user}:{user}", str(self.process_manager.status_file)], sudo=True)
                run_command(["chown", "-R", f"{user}:{user}", str(self.wireguard_config_dir)], sudo=True)
                run_command(["chown", "-R", f"{user}:{user}", str(self.openvpn_config_dir)], sudo=True)
                run_command(["chown", "-R", f"{user}:{user}", "/var/log/openvpn"], sudo=True)
            except FileNotFoundError:
                pass
            except Exception as e:
                LOG.warning(f"Could not set permissions, this might be fine: {e}")

            await self.setup_phase_1_openvpn()

            await self.setup_phase_2_start_openvpn_process()

            await self.setup_phase_3_wireguard()

            await self.setup_phase_4_add_wireguard_process()

            await self.process_manager.run()

        except Exception as e:
            LOG.error(f"WireGuard Bridge failed: {e}")
            await self.process_manager.cleanup()
            raise


@click.command()
@click.option(
    "--config-name",
    default=lambda: os.environ.get("CONFIG_NAME", "wg0"),
    help="WireGuard configuration name",
)
@click.option(
    "--health-check",
    is_flag=True,
    help="Run health check and exit",
)
def main(config_name: str, health_check: bool) -> None:
    """Main entry point for WireGuard Bridge."""

    orchestrator = WireGuardBridgeOrchestrator(config_name)
    if health_check:

        async def run_health_check():
            return await orchestrator.health_check_endpoint()

        try:
            result = asyncio.run(run_health_check())
            if result:
                LOG.success("Health check passed")
                sys.exit(0)
            else:
                LOG.error("Health check failed")
                sys.exit(1)
        except Exception as e:
            LOG.error(f"Health check error: {e}")
            sys.exit(1)
    else:
        try:
            asyncio.run(orchestrator.run())
        except KeyboardInterrupt:
            LOG.info("Received interrupt signal")
        except Exception as e:
            LOG.error(f"Failed to run WireGuard Bridge: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
