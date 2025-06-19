from ipaddress import IPv4Address, IPv4Network

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WireGuardConfig(BaseModel):
    """Pydantic model for WireGuard configuration validation"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    address_range: IPv4Network = Field(
        default_factory=lambda: IPv4Network("10.9.0.0/24", strict=False),
        description="WireGuard address range",
    )
    wg_port: int = Field(
        default=1195,
        ge=1,
        le=65535,
        description="WireGuard port number",
    )
    config_name: str = Field(
        default="wg0",
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="WireGuard config name",
    )
    public_ip: IPv4Address | None = Field(
        default=None,
        description="Public IP address for client config",
    )
    clients: list[str] = Field(
        default=["client"],
        description="List of client names or number of clients",
    )

    @field_validator("address_range", mode="before")
    @classmethod
    def validate_address_range(cls, v):
        """Validate that the address range has enough hosts"""

        if isinstance(v, str):
            v = IPv4Network(v, strict=False)

        hosts = list(v.hosts())
        if len(hosts) < 2:
            raise ValueError("Address range must have at least 2 host addresses")
        return v

    @field_validator("clients", mode="before")
    @classmethod
    def validate_clients(cls, v):
        """Convert single client count to list of client names"""

        match v:
            case int():
                if v < 1:
                    raise ValueError("Number of clients must be at least 1")
                return [f"client{i + 1}" for i in range(v)]
            case str():
                return [name.strip() for name in v.split(",") if name.strip()]
            case list():
                if len(v) == 0:
                    raise ValueError("At least one client must be specified")
                for name in v:
                    if not isinstance(name, str) or not name.strip():
                        raise ValueError("Client names must be non-empty strings")
                    if not all(c.isalnum() or c in "-_" for c in name.strip()):
                        raise ValueError(
                            f"Invalid client name '{name}': only alphanumeric, dash, and underscore allowed"
                        )
                return [name.strip() for name in v]
            case _:
                raise ValueError("Clients must be an integer, string, or list of strings")

    @model_validator(mode="after")
    def validate_enough_addresses(self):
        """Validate that address range has enough addresses for all clients"""

        if self.address_range and self.clients:
            hosts = list(self.address_range.hosts())

            required_addresses = len(self.clients) + 1
            if len(hosts) < required_addresses:
                raise ValueError(
                    f"Address range {self.address_range} has only {len(hosts)} host addresses "
                    f"but need {required_addresses} (1 server + {len(self.clients)} clients)"
                )
        return self

    @property
    def server_address(self) -> str:
        """Get the server address (first host in range)"""

        hosts = list(self.address_range.hosts())
        return f"{hosts[0]}/{self.address_range.prefixlen}"

    @property
    def client_addresses(self) -> dict[str, str]:
        """Get client addresses mapped by client name"""

        hosts = list(self.address_range.hosts())
        addresses = {}
        for i, client_name in enumerate(self.clients):
            addresses[client_name] = f"{hosts[i + 1]}/{self.address_range.prefixlen}"
        return addresses

    @property
    def client_ips(self) -> dict[str, str]:
        """Get client IPs without subnet mask mapped by client name"""

        hosts = list(self.address_range.hosts())
        ips = {}
        for i, client_name in enumerate(self.clients):
            ips[client_name] = str(hosts[i + 1])
        return ips
