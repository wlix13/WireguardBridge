FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --no-dev

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.authors="Renat Mustafin <mustafinrr.rm@gmail.com>"

ENV PATH="/app/.venv/bin:$PATH" \
    TZ=Europe/Moscow \
    USER=bridge \
    STATUS_FILE=/run/process_status.json \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --no-install-recommends -y \
    sudo \
    wireguard-tools \
    openvpn \
    iptables \
    iproute2 \
    curl \
    tini \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv

RUN mkdir -p /etc/wireguard /etc/wireguard/keys /etc/wireguard/clients /etc/openvpn \
    && touch $STATUS_FILE \
    && adduser --system --no-create-home --disabled-password --group bridge \
    && echo "bridge ALL=(ALL) NOPASSWD: /bin/chown, /sbin/sysctl, /sbin/iptables, /usr/sbin/openvpn, /usr/bin/wg-quick" > /etc/sudoers.d/bridge

USER bridge

HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=3 \
    CMD bridge --health-check

ENTRYPOINT ["tini", "--", "bridge"]
