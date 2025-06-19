# Configuration

## Environment Variables

| Variable           | Default       | Description                                   |
| ------------------ | ------------- | --------------------------------------------- |
| `WG_PORT`          | `1195`        | WireGuard listening port                      |
| `CONFIG_NAME`      | `wg0`         | WireGuard interface name (server config name) |
| `WG_CLIENTS`       | `client`      | Comma-separated client names                  |
| `WG_ADDRESS_RANGE` | `10.9.0.0/24` | WireGuard address range                       |
| `PUBLIC_IP`        | auto-detected | Public IP for client configs                  |

## Volume Mounts

| Container Path        | Purpose                     | Required                  |
| --------------------- | --------------------------- | ------------------------- |
| `/etc/openvpn/config` | OpenVPN configuration files | ✅ Yes                    |
| `/etc/wireguard`      | WireGuard keys and configs  | ⚠️ **Highly Recommended** |
| `/var/log/openvpn`    | OpenVPN logs                | ❌ Optional               |

### WireGuard keys and configs

Server keys and client configs can be mounted separately. If you don't mount the WireGuard directory, the container will generate a new set of keys and configs.

```bash
-v ./bridge/wireguard:/etc/wireguard:Z
```

```bash
-v ./bridge/wireguard/clients:/etc/wireguard/clients:Z -v ./bridge/wireguard/keys:/etc/wireguard/keys:Z
```

## Advanced Configuration

### Multiple Clients

To create configurations for multiple clients, provide a comma-separated list of names in the `WG_CLIENTS` environment variable.

```bash
-e WG_CLIENTS="number1,number2,number3"
# Creates: number1.conf, number2.conf, number3.conf
```

Or you can just enter number of clients in the `WG_CLIENTS` environment variable and the container will generate the necessary number of clients.

```bash
-e WG_CLIENTS=3
# Creates: client1.conf, client2.conf, client3.conf
```

### Adding client in runtime

You can add a client in runtime by executing command in the container.

```bash
docker exec -it wireguardbridge setup_wireguard add-client test
```

This will create a new client named `test` and automatically restart the WireGuard service. However, if you have not mounted the entire `/etc/wireguard` directory (for example, if you are only mounting the `clients` and `keys` subfolders), the new client will not be added to the server configuration after a container restart. In this case, you must also add the client name to the `WG_CLIENTS` environment variable to ensure it is included in the configuration on startup.

### Custom Network Range

You can customize the IP address range for the WireGuard network using the `WG_ADDRESS_RANGE` environment variable.

```bash
-e WG_ADDRESS_RANGE="10.8.0.0/24"
# Server: 10.8.0.1, Clients: 10.8.0.2, 10.8.0.3, etc.
```

### Static Public IP

If the container cannot automatically detect the public IP or you want to use a specific one, set it with the `PUBLIC_IP` environment variable.

```bash
-e PUBLIC_IP="10.8.0.1"
```
