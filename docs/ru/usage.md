# Использование

## Быстрый старт

Самый быстрый способ начать использовать - готовый ÷образ из GitHub Container Registry.

### Пример запуска контейнера

```bash
docker run -d \
  --name wireguard-bridge \
  --privileged \
  -p 1195:1195/udp \ # Порт по умолчанию для WireGuard
  -v /path/to/openvpn/config:/etc/openvpn/config:ro \ # Файлы конфигурации OpenVPN
  -v /path/to/wireguard/data:/etc/wireguard \ # Сохранение ключей и конфигурации WireGuard
  ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
```

### 🔑 ВАЖНО: Сохранение ключей и конфигурации

Чтобы предотвратить недействительность конфигураций клиентов после перезапуска контейнера, **вы ДОЛЖНЫ смонтировать каталог WireGuard**:

```bash
-v /path/to/wireguard/data:/etc/wireguard
```

Или вы можете смонтировать только подпапки `clients` и `keys`.

```bash
docker run -d \
  --name wireguard-bridge \
  --privileged \
  -e WG_PORT=1194 \ # Порт WireGuard
  -p 1194:1194/udp \ # Порт WireGuard
  -v /path/to/openvpn/config:/etc/openvpn/config:ro \ # Файлы конфигурации OpenVPN
  -v /path/to/wireguard/clients:/etc/wireguard/clients:Z \ # Клиентские конфигурации WireGuard
  -v /path/to/wireguard/keys:/etc/wireguard/keys:Z \ # Ключи сервера WireGuard (для восстановления ключей сервера после перезапуска контейнера)
  ghcr.io/wlix13/wireguardbridge/wireguardbridge:v1.0
```

Информация про переменные окружения: [Конфигурация](configuration.md)

## Проверки работоспособности

Контейнер включает встроенный мониторинг:

```bash
# Проверить статус контейнера
docker ps | grep wireguard-bridge  # Должен быть статус "healthy"

# Ручная проверка статуса
docker exec wireguard-bridge bridge --health-check
```

## Пример Docker Compose

Для более декларативной настройки есть пример `docker-compose` файла.

### Один мост (пример)

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

Структура каталогов будет выглядеть так:

```plaintext
.
├── docker-compose.yml
├── openvpn/
│   └── your-config.ovpn   # Ваш файл конфигурации клиента OpenVPN (или файл .conf)
│   └── ...                # Другие файлы, связанные с OpenVPN
└── wireguard/             # Этот каталог будет использоваться для сохранения ключей и конфигурации WireGuard
│   └── clients/            # Здесь будут храниться конфигурации клиентов
│   └── keys/              # Здесь будут храниться ключи сервера WireGuard
│   └── wg0.conf           # Файл конфигурации сервера WireGuard
│   └── ...                # Другие файлы, связанные с WireGuard
```

### Несколько мостов (пример)

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

Структура каталогов будет выглядеть так:

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
