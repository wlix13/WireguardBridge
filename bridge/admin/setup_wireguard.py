import json
import os
import signal
import time
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

import click
from jinja2 import Environment, PackageLoader
from python_wireguard import Key

from bridge.admin.shell_wrapper import run_command
from bridge.logger import LOG
from bridge.models import WireGuardConfig


class WireGuardSetup:
    """WireGuard setup and configuration management"""

    def __init__(self, config: WireGuardConfig):
        self.config = config

        self.server_dir = Path("/etc/wireguard")
        self.server_keys_dir = Path("/etc/wireguard/keys")
        self.clients_dir = Path("/etc/wireguard/clients")

        self.server_private_key_file = self.server_keys_dir / "private.key"
        self.server_public_key_file = self.server_keys_dir / "public.key"
        self.server_config_file = self.server_dir / f"{self.config.config_name}.conf"

        self.jinja_env = Environment(
            loader=PackageLoader("bridge", "templates"),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    @classmethod
    def from_config(cls, config: WireGuardConfig) -> "WireGuardSetup":
        """Create WireGuardSetup from pydantic config"""

        instance = cls(config)

        instance.clients_dir.mkdir(parents=True, exist_ok=True)
        instance.server_dir.mkdir(parents=True, exist_ok=True)
        instance.server_keys_dir.mkdir(parents=True, exist_ok=True)

        LOG.debug(f"Using address range: {config.address_range}")
        LOG.debug(f"Server address: {config.server_address}")
        LOG.debug(f"Clients: '{', '.join(config.clients)}'")

        return instance

    @classmethod
    def from_click_options(
        cls,
        wg_port: int,
        config_name: str,
        public_ip: IPv4Address | None,
        address_range: IPv4Network,
        clients: str | list[str],
    ) -> "WireGuardSetup":
        """Create WireGuardSetup from Click options"""

        config = WireGuardConfig(
            address_range=address_range,
            wg_port=wg_port,
            config_name=config_name,
            public_ip=public_ip,
            clients=clients.split(",") if isinstance(clients, str) else clients,
        )
        return cls.from_config(config)

    @staticmethod
    def get_external_ip() -> str:
        """Get external IP address for client config"""

        providers = [
            "ifconfig.co",
            "ifconfig.me",
            "icanhazip.com",
        ]

        for provider in providers:
            try:
                result = run_command(
                    [
                        "curl",
                        "-s",
                        "--max-time",
                        "10",
                        provider,
                    ]
                )
                if result.returncode == 0 and result.stdout.strip():
                    LOG.info(f"External IP detected via {provider}: {result.stdout.strip()}")
                    return result.stdout.strip()
                else:
                    LOG.warning(f"Could not get external IP from {provider} (returncode={result.returncode})")
            except Exception as e:
                LOG.warning(f"Could not get external IP from {provider}: {e}")

        LOG.error("All external IP providers failed. Using placeholder IP.")
        return "YOUR_SERVER_IP"

    def wait_for_tun_interface(self, timeout: int = 30) -> str:
        """Wait for OpenVPN tunnel interface to appear"""

        LOG.info("Waiting for OpenVPN tunnel interface...")

        for i in range(timeout):
            try:
                result = run_command(["ip", "addr"])
                if "tun" in result.stdout:
                    for line in result.stdout.split("\n"):
                        if "tun" in line and ":" in line:
                            tun_name = line.split(":")[1].strip().split("@")[0]
                            LOG.info(f"OpenVPN tunnel interface detected: {tun_name}")
                            return tun_name

                time.sleep(1)
                if i % 5 == 0:
                    LOG.info(f"Waiting for tun interface... ({i}/{timeout})")

            except Exception as e:
                LOG.warning(f"Error checking for tun interface: {e}")
                time.sleep(1)

        raise Exception("OpenVPN tunnel interface not found after timeout")

    def get_server_keys(self) -> tuple[Key, Key]:
        """Generate or load WireGuard server keys"""

        if self.server_private_key_file.exists() and self.server_public_key_file.exists():
            LOG.info("Using existing server keys - client configs remain valid")
            try:
                with (
                    open(self.server_private_key_file) as private_key_file,
                    open(self.server_public_key_file) as public_key_file,
                ):
                    private_key_str = private_key_file.read().strip()
                    public_key_str = public_key_file.read().strip()

                private_key = Key(private_key_str)
                public_key = Key(public_key_str)

                return private_key, public_key

            except Exception as e:
                LOG.error(f"Failed to load existing keys: {e}")
                LOG.warning("Falling back to generating new keys - client configs will need updating!")
        else:
            LOG.warning("No existing server keys found")

        LOG.info("Generating new server keys")
        LOG.warning("⚠️  IMPORTANT: Client configurations will need to be updated with the new server public key!")
        LOG.warning("⚠️  To persist keys across container restarts, don't forget to mount /etc/wireguard as a volume")

        private_key, public_key = Key.key_pair()

        try:
            with (
                open(self.server_private_key_file, "w") as private_key_file,
                open(self.server_public_key_file, "w") as public_key_file,
            ):
                private_key_file.write(str(private_key))
                public_key_file.write(str(public_key))

            os.chmod(self.server_private_key_file, 0o600)
            os.chmod(self.server_public_key_file, 0o644)

        except Exception as e:
            LOG.error(f"Failed to save server keys: {e}")
            raise

        return private_key, public_key

    def get_client_keys(self) -> dict[str, tuple[Key, Key]]:
        """Generate or load WireGuard client keys for all clients"""

        client_keys = {}

        for client_name in self.config.clients:
            private_key_file = self.clients_dir / f"{client_name}_private.key"
            public_key_file = self.clients_dir / f"{client_name}_public.key"

            if private_key_file.exists() and public_key_file.exists():
                LOG.info(f"Using existing keys for client {client_name}")
                with (
                    open(private_key_file) as private_file,
                    open(public_key_file) as public_file,
                ):
                    private_key_str = private_file.read().strip()
                    public_key_str = public_file.read().strip()

                private_key = Key(private_key_str)
                public_key = Key(public_key_str)
            else:
                LOG.info(f"Generating new keys for client {client_name}")
                private_key, public_key = Key.key_pair()

                with (
                    open(private_key_file, "w") as private_file,
                    open(public_key_file, "w") as public_file,
                ):
                    private_file.write(str(private_key))
                    public_file.write(str(public_key))

                os.chmod(private_key_file, 0o600)
                os.chmod(public_key_file, 0o644)

            client_keys[client_name] = (private_key, public_key)

        return client_keys

    def create_client_configs(
        self,
        client_keys: dict[str, tuple[Key, Key]],
        server_public_key: Key,
        external_ip: str,
        table: bool = True,
        force_recreate: bool = False,
    ) -> None:
        """Create WireGuard client configuration files for all clients"""

        client_template = self.jinja_env.get_template("client.conf.j2")

        for client_name, (client_private_key, client_public_key) in client_keys.items():
            client_config_file = self.clients_dir / f"{client_name}.conf"

            if client_config_file.exists() and not force_recreate:
                try:
                    with open(client_config_file) as f:
                        config_content = f.read()

                    if str(server_public_key) in config_content:
                        LOG.info(
                            f"Client configuration {client_config_file} already exists with correct server key. "
                            "Skipping."
                        )
                        continue
                    else:
                        LOG.warning(f"Client configuration {client_config_file} has outdated server key. Recreating.")
                except Exception as e:
                    LOG.warning(f"Could not verify client config {client_config_file}: {e}. Recreating.")

            client_address = self.config.client_addresses[client_name]

            client_config = client_template.render(
                private_key=client_private_key,
                address=client_address,
                table=table,
                server_public_key=server_public_key,
                external_ip=external_ip,
                wg_port=self.config.wg_port,
            )

            with open(client_config_file, "w") as f:
                f.write(client_config)

    def create_server_config(
        self,
        server_private_key: Key,
        client_keys: dict[str, tuple[Key, Key]],
        tun_interface: str,
    ) -> None:
        """Create WireGuard server configuration with iptables rules and multiple client peers"""

        if self.server_config_file.exists():
            LOG.info("Server configuration already exists. Skipping.")
            return

        server_template = self.jinja_env.get_template("server.conf.j2")
        peer_template = self.jinja_env.get_template("peer.conf.j2")

        peer_sections = []
        for client_name, (client_private_key, client_public_key) in client_keys.items():
            client_ip = self.config.client_ips[client_name]
            peer_section = peer_template.render(
                public_key=client_public_key,
                allowed_ip=client_ip,
            )
            peer_sections.append(peer_section)

        server_config = server_template.render(
            server_address=self.config.server_address,
            wg_port=self.config.wg_port,
            private_key=server_private_key,
            tun_interface=tun_interface,
            peers=peer_sections,
        )

        with open(self.server_config_file, "w") as f:
            f.write(server_config)
        os.chmod(self.server_config_file, 0o600)

        LOG.info(f"Added {len(client_keys)} client peers to server config")

    def setup(self) -> str:
        """Main setup method"""

        try:
            tun_interface = self.wait_for_tun_interface()

            server_private_key, server_public_key = self.get_server_keys()
            client_keys = self.get_client_keys()

            external_ip = os.environ.get("PUBLIC_IP")
            if not external_ip:
                LOG.warning("PUBLIC_IP not set, attempting to get external IP")
                external_ip = self.get_external_ip()

            has_existing_server_config = self.server_config_file.exists()
            has_existing_client_configs = any(
                (self.clients_dir / f"{client}.conf").exists() for client in self.config.clients
            )
            # Force recreate client configs if server key changed (new setup or key regeneration)
            force_recreate_clients = not (has_existing_server_config and has_existing_client_configs)

            self.create_client_configs(
                client_keys,
                server_public_key,
                external_ip,
                force_recreate=force_recreate_clients,
            )

            self.create_server_config(
                server_private_key,
                client_keys,
                tun_interface,
            )

            setup_info = {
                "config_name": self.config.config_name,
                "wg_port": self.config.wg_port,
                "tun_interface": tun_interface,
                "server_public_key": str(server_public_key),
                "external_ip": external_ip,
            }

            with open("/tmp/wg-setup-info.json", "w") as f:  # noqa: S108
                json.dump(setup_info, f, indent=2)

            return str(self.server_config_file)

        except Exception as e:
            LOG.error(f"WireGuard setup failed: {e}")
            raise


@click.group()
def main():
    """WireGuard server configuration and client management."""


@main.command("setup")
@click.option(
    "--wg-port",
    default=lambda: os.environ.get("WG_PORT", 1195),
    show_default=True,
    help="WireGuard port",
)
@click.option(
    "--config-name",
    default=lambda: os.environ.get("CONFIG_NAME", "wg0"),
    show_default=True,
    help="WireGuard config name",
)
@click.option(
    "--public-ip",
    help="Public IP address for client config",
)
@click.option(
    "--address-range",
    default=lambda: os.environ.get("WG_ADDRESS_RANGE", "10.9.0.0/24"),
    type=IPv4Network,
    show_default=True,
    help="WireGuard address range (server gets first host, clients get subsequent hosts)",
)
@click.option(
    "--clients",
    default=lambda: os.environ.get("WG_CLIENTS", "client"),
    help="Comma-separated client names or number of clients (e.g., 'client1,client2' or '3')",
)
def setup_command(
    wg_port: int,
    config_name: str,
    public_ip: IPv4Address | None,
    address_range: IPv4Network,
    clients: str,
):
    """Initializes WireGuard server configuration and clients."""

    wireguard_setup = WireGuardSetup.from_click_options(
        wg_port=wg_port,
        config_name=config_name,
        public_ip=public_ip,
        address_range=address_range,
        clients=clients,
    )
    wireguard_setup.setup()


@main.command("add-client")
@click.argument("client_name")
@click.option(
    "--config-name",
    default=lambda: os.environ.get("CONFIG_NAME", "wg0"),
    show_default=True,
    help="WireGuard config name. Should match running instance.",
)
@click.option(
    "--address-range",
    default=lambda: os.environ.get("WG_ADDRESS_RANGE", "10.9.0.0/24"),
    type=IPv4Network,
    show_default="env: WG_ADDRESS_RANGE or 10.9.0.0/24",
    help="WireGuard address range. MUST match server's existing config.",
)
def add_client_command(client_name: str, config_name: str, address_range: IPv4Network):
    """Adds a new WireGuard client and restarts the service."""

    setup_info_file = Path("/tmp/wg-setup-info.json")  # noqa: S108
    if not setup_info_file.exists():
        LOG.error("Setup info file not found. Please run setup first.")
        raise click.ClickException("Setup info not found.")

    with open(setup_info_file) as f:
        setup_info = json.load(f)

    clients_dir = Path("/etc/wireguard/clients")
    existing_clients = [p.stem for p in clients_dir.glob("*.conf")]

    if client_name in existing_clients:
        LOG.error(f"Client '{client_name}' already exists.")
        raise click.ClickException(f"Client '{client_name}' already exists.")

    all_clients = existing_clients + [client_name]

    wireguard_setup = WireGuardSetup.from_click_options(
        wg_port=setup_info["wg_port"],
        config_name=config_name,
        public_ip=setup_info["external_ip"],
        address_range=address_range,
        clients=all_clients,
    )

    LOG.info(f"Generating keys for new client '{client_name}'")
    all_client_keys = wireguard_setup.get_client_keys()

    server_public_key = Key(setup_info["server_public_key"])
    external_ip = setup_info["external_ip"]

    wireguard_setup.create_client_configs(
        {client_name: all_client_keys[client_name]},
        server_public_key,
        external_ip,
        force_recreate=True,
    )
    LOG.success(f"Generated configuration for client '{client_name}'")

    LOG.info("Appending new peer to server configuration...")
    peer_template = wireguard_setup.jinja_env.get_template("peer.conf.j2")
    new_client_public_key = all_client_keys[client_name][-1]
    new_client_ip = wireguard_setup.config.client_ips[client_name]

    peer_section = peer_template.render(
        public_key=new_client_public_key,
        allowed_ip=new_client_ip,
    )

    server_config_file = wireguard_setup.server_config_file
    with open(server_config_file, "a") as f:
        f.write(f"\n{peer_section}")

    LOG.success(f"Added peer for '{client_name}' to {server_config_file}")

    LOG.info("Restarting WireGuard process to apply changes...")
    # TODO: use ProcessManager to restart WireGuard process
    status_file = Path("/run/process_status.json")
    if not status_file.exists():
        LOG.error("Process status file not found. Cannot restart WireGuard process.")
        raise click.ClickException("Process status file not found. Cannot restart WireGuard.")

    with open(status_file) as f:
        statuses = json.load(f)

    wg_status = statuses.get("wireguard")
    if not wg_status or not wg_status.get("pid"):
        LOG.error("WireGuard process not found in status file.")
        raise click.ClickException("WireGuard process not found in status file.")

    pid = wg_status["pid"]
    try:
        os.kill(pid, signal.SIGTERM)
        LOG.success(f"Sent SIGTERM to WireGuard process (PID: {pid}). It should restart automatically.")
    except ProcessLookupError:
        LOG.warning(f"Process with PID {pid} not found. It might have already exited.")
    except Exception as e:
        LOG.error(f"Failed to kill WireGuard process: {e}")
        raise click.ClickException("Failed to restart WireGuard process.")


if __name__ == "__main__":
    main()
