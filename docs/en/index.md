# Welcome to WireGuard Bridge - bridge for WireGuard and OpenVPN

Docker container that bridges WireGuard clients to OpenVPN servers, providing a seamless way to route WireGuard traffic through existing OpenVPN connections.

## Features

- **Zero-config setup**: Just mount the OpenVPN configuration files and the WireGuard directory and the container will do the rest.
- **Key persistence**: Maintains consistent server keys across container restarts when properly configured
- **Health Monitoring & Automatic Restart**: Built-in health checks for both OpenVPN and WireGuard processes with automatic restart on failure.
- **Client management**: Automatic generation of client configurations. You can specify the number of clients or the names of the clients.
- **Python-based**: Fully Python-controlled process management with additional control over running container.

## Attention

This container requires the `--privileged` flag because it uses `sysctl` to configure forwarding rules. Despite this, the container runs processes as a non-root user with limited permissions for improved security.

This documentation provides detailed information on how to use, configure, and troubleshoot the WireGuard Bridge.
