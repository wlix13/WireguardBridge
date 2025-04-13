# Podman

## Build

podman build --security-opt label=disable --platform linux/amd64 -t wireguard-bridge .

## Run

podman run -d --platform linux/amd64 --name wireguard-bridge --restart unless-stopped \
 --cap-add NET_ADMIN \
 --cap-add SYS_MODULE \
 --privileged \
 -p 1195:1195/udp \
 -v ./openvpn:/etc/openvpn/config:Z \
 -v ./wireguard:/etc/wireguard/client:Z \
 wireguard-bridge

# Docker

## Build

docker build --platform linux/amd64 -t wireguard-bridge .

## Run

docker run -d --platform linux/amd64 --name wireguard-bridge --restart unless-stopped \
 --cap-add NET_ADMIN \
 --cap-add SYS_MODULE \
 --privileged \
 -p 1195:1195/udp \
 -v ~/wireguard-bridge/openvpn:/etc/openvpn/config:Z \
 -v ~/wireguard-bridge/wireguard:/etc/wireguard/client:Z \
 wireguard-bridge
