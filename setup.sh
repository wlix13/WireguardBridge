#!/bin/bash
set -e

echo "Starting OpenVPN client and WireGuard server container..."

# Find OpenVPN config
OPENVPN_CONFIG=""
if [ -d /etc/openvpn/config ] && [ "$(ls -A /etc/openvpn/config)" ]; then
    for CONFIG in /etc/openvpn/config/*.ovpn /etc/openvpn/config/*.conf; do
        if [ -f "$CONFIG" ]; then
            OPENVPN_CONFIG="$CONFIG"
            echo "Found OpenVPN config: $OPENVPN_CONFIG"
            break
        fi
    done
fi

if [ -z "$OPENVPN_CONFIG" ]; then
    echo "Error: No OpenVPN configuration found in /etc/openvpn/config"
    exit 1
fi

# Enable IP forwarding immediately
echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.forwarding=1
sysctl -w net.ipv6.conf.all.forwarding=1

# Start OpenVPN client in the background
echo "Starting OpenVPN client..."
# Add logging to help with debugging
mkdir -p /var/log/openvpn/
openvpn --config "$OPENVPN_CONFIG" --log /var/log/openvpn/openvpn.log --daemon

# Wait for tun interface to be created by OpenVPN
echo "Waiting for OpenVPN tun interface..."
timeout=30
counter=0
TUN_INTERFACE=""

while [ $counter -lt $timeout ]; do
    TUN_INTERFACE=$(ip addr | grep -o "tun[0-9]*" | head -n 1)
    if [ -n "$TUN_INTERFACE" ]; then
        echo "OpenVPN tunnel interface detected: $TUN_INTERFACE"
        break
    fi
    echo "Waiting for tun interface to appear... ($counter/$timeout)"
    sleep 1
    counter=$((counter + 1))
done

if [ -z "$TUN_INTERFACE" ]; then
    echo "Error: OpenVPN tun interface not found after $timeout seconds"
    cat /var/log/openvpn/openvpn.log
    exit 1
fi

# Check OpenVPN connection
echo "OpenVPN routes:"
ip route | grep "$TUN_INTERFACE"

# Create client directory if it doesn't exist
mkdir -p /etc/wireguard/client

# Check for existing WireGuard configuration
CLIENT_CONFIG="/etc/wireguard/client/client.conf"
CLIENT_PRIVATE_KEY="/etc/wireguard/client/private.key"
CLIENT_PUBLIC_KEY="/etc/wireguard/client/public.key"

# Generate WireGuard server keys if they don't exist
if [ ! -f /etc/wireguard/privatekey ] || [ ! -f /etc/wireguard/publickey ]; then
    echo "Generating WireGuard server keys..."
    cd /etc/wireguard
    wg genkey | tee privatekey | wg pubkey > publickey
    chmod 600 privatekey
fi

SERVER_PRIVATE_KEY=$(cat /etc/wireguard/privatekey)
SERVER_PUBLIC_KEY=$(cat /etc/wireguard/publickey)

# Check if client keys exist, generate if not
if [ ! -f "$CLIENT_PRIVATE_KEY" ] || [ ! -f "$CLIENT_PUBLIC_KEY" ]; then
    echo "Generating new WireGuard client keys..."
    CLIENT_PRIVATE_KEY_VALUE=$(wg genkey)
    echo "$CLIENT_PRIVATE_KEY_VALUE" > "$CLIENT_PRIVATE_KEY"
    echo "$CLIENT_PRIVATE_KEY_VALUE" | wg pubkey > "$CLIENT_PUBLIC_KEY"
    chmod 600 "$CLIENT_PRIVATE_KEY"

    # Create client config
    echo "Creating new client configuration..."
    cat > "$CLIENT_CONFIG" << EOF
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY_VALUE}
Address = 10.9.0.2/24
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = $(curl -s ifconfig.co):${WG_PORT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
    echo "New client configuration created at $CLIENT_CONFIG"
else
    echo "Using existing client configuration from $CLIENT_CONFIG"
fi

# Read client public key
CLIENT_PUBLIC_KEY_VALUE=$(cat "$CLIENT_PUBLIC_KEY")

# Create WireGuard configuration
echo "Configuring WireGuard to route through OpenVPN tunnel ($TUN_INTERFACE)..."
cat > /etc/wireguard/${CONFIG_NAME}.conf << EOF
[Interface]
Address = 10.9.0.1/24
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIVATE_KEY}
Table = off

# Forward WireGuard traffic through OpenVPN tunnel
PostUp = iptables -A FORWARD -i %i -o ${TUN_INTERFACE} -j ACCEPT
PostUp = iptables -A FORWARD -o %i -i ${TUN_INTERFACE} -j ACCEPT
PostUp = iptables -t nat -A POSTROUTING -o ${TUN_INTERFACE} -j MASQUERADE
# Enable masquerading for all interfaces to ensure traffic flows properly
PostUp = iptables -t nat -A POSTROUTING -j MASQUERADE

# Cleanup rules when stopping
PostDown = iptables -D FORWARD -i %i -o ${TUN_INTERFACE} -j ACCEPT
PostDown = iptables -D FORWARD -o %i -i ${TUN_INTERFACE} -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -o ${TUN_INTERFACE} -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -j MASQUERADE

[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY_VALUE}
AllowedIPs = 10.9.0.2/32
EOF

# Copy the client config to /etc/wireguard for backward compatibility
cp "$CLIENT_CONFIG" /etc/wireguard/client.conf

echo "Starting WireGuard..."
wg-quick up ${CONFIG_NAME}

# Display network information
echo "Network configuration:"
ip addr
echo -e "\nRoutes:"
ip route
echo -e "\niptables NAT rules:"
iptables -t nat -L
echo -e "\niptables FORWARD rules:"
iptables -L FORWARD

echo -e "\nWireGuard configuration:"
wg show

# Keep container running
echo "OpenVPN client and WireGuard server are running. Press Ctrl+C to stop."
tail -f /var/log/openvpn/openvpn.log
