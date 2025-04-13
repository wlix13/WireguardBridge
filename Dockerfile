FROM ubuntu:24.04

# Set noninteractive installation
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y \
    wireguard \
    wireguard-tools \
    openvpn \
    iptables \
    iproute2 \
    net-tools \
    iputils-ping \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create directories for configuration files
RUN mkdir -p /etc/wireguard /etc/openvpn

# Set environment variables with defaults (can be overridden at runtime)
ENV WG_PORT=1195
ENV CONFIG_NAME=wg0

# Copy the conversion and setup script
COPY ./setup.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup.sh

# Volumes for configuration
VOLUME ["/etc/openvpn/config"]
VOLUME ["/etc/wireguard/client"]

# Start script
CMD ["/usr/local/bin/setup.sh"]
