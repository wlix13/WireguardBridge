# Usage

## Quick Start

The quickest way to get started is by using the pre-built Docker container from GitHub Container Registry.

### Mounting wireguard directory

```bash
docker run -d \
  --name wireguard-bridge \
  --privileged \
  -p 1195:1195/udp \ # Default port for WireGuard
  -v /path/to/openvpn/config:/etc/openvpn/config:ro \ # OpenVPN configuration files
  -v /path/to/wireguard/data:/etc/wireguard \ # WireGuard key and config persistence
  ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
```

### 🔑 IMPORTANT: Key Persistence

To prevent client configurations from becoming invalid after container restarts, **you MUST mount the WireGuard directory as a volume**:

```bash
-v /path/to/wireguard/data:/etc/wireguard
```

Or you can mount only the `clients` and `keys` subfolders.

```bash
docker run -d \
  --name wireguard-bridge \
  --privileged \
  -e WG_PORT=1194 \ # WireGuard port
  -p 1194:1194/udp \ # WireGuard port
  -v /path/to/openvpn/config:/etc/openvpn/config:ro \ # OpenVPN configuration files
  -v /path/to/wireguard/clients:/etc/wireguard/clients:Z \ # WireGuard client configs
  -v /path/to/wireguard/keys:/etc/wireguard/keys:Z \ # WireGuard server keys(to restore server keys after container restart)
  ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
```

Environment variables information: [Configuration](configuration.md)

## Health Checks

The container includes built-in health monitoring:

```bash
# Check container health
docker ps | grep wireguard-bridge  # Should be "healthy" status

# Manual health check
docker exec wireguard-bridge bridge --health-check
```

## Docker Compose Example

For a more declarative setup, there is an example `docker-compose` file.

### Single Bridge (example)

```yaml
services:
  wg-bridge:
    image: ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
    container_name: wg-bridge
    restart: unless-stopped
    privileged: true
    ports:
      - "1195:1195/udp"
    volumes:
      - ./openvpn:/etc/openvpn/config:Z
      - ./wireguard:/etc/wireguard:Z
```

Your directory structure should look like this:

```plaintext
.
├── docker-compose.yml
├── openvpn/
│   └── your-config.ovpn   # Your OpenVPN client configuration file (or .conf file)
│   └── ...                # Other OpenVPN related files
└── wireguard/             # This directory will be used for WireGuard key and config persistence
│   └── clients/            # Client configurations will be stored here
│   └── keys/              # WireGuard Server keys will be stored here
│   └── wg0.conf           # WireGuard Server config file
│   └── ...                # Other WireGuard related files
```

### Multiple Bridges (example)

```yaml
services:
  wg-bridge-1:
    image: ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
    container_name: wg-bridge-1
    restart: unless-stopped
    privileged: true
    ports:
      - "1195:1195/udp"
    environment:
      - WG_PORT=1195
    volumes:
      - ./bridges/bridge-1/openvpn:/etc/openvpn/config:Z
      - ./bridges/bridge-1/wireguard/clients:/etc/wireguard/clients:Z
      - ./bridges/bridge-1/wireguard/keys:/etc/wireguard/keys:Z
  wg-bridge-2:
    image: ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
    container_name: wg-bridge-2
    restart: unless-stopped
    privileged: true
    ports:
      - "1194:1194/udp"
    environment:
      - WG_PORT=1194
    volumes:
      - ./bridges/bridge-2/openvpn:/etc/openvpn/config:Z
      - ./bridges/bridge-2/wireguard/clients:/etc/wireguard/clients:Z
      - ./bridges/bridge-2/wireguard/keys:/etc/wireguard/keys:Z
```

Your directory structure should look like this:

```plaintext
.
├── docker-compose.yml
├── bridges/
│   └── bridge-1/
│       └── openvpn/
│           └── your-config.ovpn
│           └── ...
│       └── wireguard/
│           └── clients/
│           └── keys/
│           └── ...
│   └── bridge-2/
│       └── openvpn/
│           └── your-config.ovpn
│           └── ...
│       └── wireguard/
│           └── clients/
│           └── keys/
│           └── ...
```
