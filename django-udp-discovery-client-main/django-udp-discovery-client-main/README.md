# django-udp-discovery-client

Pure Python client for discovering [django-udp-discovery](https://github.com/Ogro-Projukti/django-udp-discovery) servers on local networks via UDP broadcast. No Django required for core usage.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Django Integration](#django-integration)
- [Configuration](#configuration)
- [Optional encrypted discovery (Fernet)](#optional-encrypted-discovery-fernet)
- [Verifying Installation](#verifying-installation)
- [Logging](#logging)
- [Technical Considerations](#technical-considerations)
- [Requirements](#requirements)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Broadcast discovery** — Send UDP discovery requests and collect `SERVER_IP:` responses from servers on the same broadcast domain.
- **Multi-interface support** — Discover across all (or selected) IPv4 interfaces; broadcast per interface, deduplicate results by `(ip, port)`. Requires the `[network]` extra.
- **Django integration (optional)** — Management command `python manage.py discover_servers` when `discovery_client_django` is in `INSTALLED_APPS`; install with `[django]` extra.
- **Configurable** — `ClientConfig` / `load_config()` with env vars (`DISCOVERY_CLIENT_*`) and runtime overrides; interface whitelist/blacklist.
- **Cross-platform** — Windows, Linux, macOS. Optional deps: `netifaces` or `ifaddr` for interface enumeration, Django for the management command.
- **Optional Fernet encryption** — Match server `DISCOVERY_ENCRYPTION_ENABLED` using the same pre-shared key; see [Optional encrypted discovery (Fernet)](#optional-encrypted-discovery-fernet).

---

## Installation

**Base install** (core only; multi-interface discovery needs interface enumeration and will fail without the network extra):

```bash
pip install django-udp-discovery-client
```

**Recommended** — with network support for multi-interface discovery (requires `netifaces` or `ifaddr`):

```bash
pip install django-udp-discovery-client[network]
```

**With Django** (for the management command only):

```bash
pip install django-udp-discovery-client[django]
```

**All extras**:

```bash
pip install django-udp-discovery-client[all]
```

**From source**:

```bash
git clone https://github.com/Ogro-Projukti/django-udp-discovery-client.git
cd django-udp-discovery-client
pip install .
pip install ".[network]"   # recommended for multi-interface
```

---

## Quick Start

### Basic Python (no Django)

```python
from discovery_client import discover, discover_one

# Discover all servers
servers = discover()
for s in servers:
    print(f"{s.ip}:{s.port}")  # DiscoveryResult

# Or just the first
server = discover_one()
if server:
    print(server.ip, server.port)
```

### Django: server setup and management command

**1. Server** (django-udp-discovery) — in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_udp_discovery',
]
# Optional: DISCOVERY_PORT = 9999, DISCOVERY_MESSAGE = "DISCOVER_SERVER", etc.
```

**2. Client** — discover from any Python script or from Django:

```python
from discovery_client import discover
servers = discover()
for s in servers:
    url = f"http://{s.ip}:{s.port}"
```

**3. Optional Django integration** — in your Django project `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'discovery_client_django',
]
```

Then run:

```bash
python manage.py discover_servers
python manage.py discover_servers --timeout 10.0 --port 9999 --verbose
```

---

## Configuration

Use `ClientConfig` or `load_config()`. Priority: **defaults** &lt; **environment variables** (`DISCOVERY_CLIENT_*`) &lt; **keyword overrides**.

| Environment variable | Description | Example |
|----------------------|-------------|---------|
| `DISCOVERY_CLIENT_PORT` | Discovery UDP port | `9999` |
| `DISCOVERY_CLIENT_MESSAGE` | Discovery message | `DISCOVER_SERVER` |
| `DISCOVERY_CLIENT_RESPONSE_PREFIX` | Response prefix | `SERVER_IP:` |
| `DISCOVERY_CLIENT_TIMEOUT` | Timeout (seconds) | `5.0` |
| `DISCOVERY_CLIENT_RETRIES` | Retries (reserved) | `3` |
| `DISCOVERY_CLIENT_ENABLE_SUBNET_SCAN` | Subnet scan (reserved) | `true` |
| `DISCOVERY_CLIENT_INTERFACES_WHITELIST` | Comma-separated interface names | `eth0,wlan0` |
| `DISCOVERY_CLIENT_INTERFACES_BLACKLIST` | Comma-separated interface names | `docker0,lo` |
| `DISCOVERY_CLIENT_ENCRYPTION_ENABLED` or `DISCOVERY_ENCRYPTION_ENABLED` | Fernet discovery mode | `true` |
| `DISCOVERY_CLIENT_SECRET_KEY` or `DISCOVERY_SECRET_KEY` | Fernet key (must match server) | (key from `Fernet.generate_key()`) |

Example with overrides:

```python
from discovery_client import load_config, discover
config = load_config(timeout=10.0, discovery_port=8888)
servers = discover(config=config)
```

Interface filtering: `ClientConfig(interfaces_whitelist=["eth0"], interfaces_blacklist=["docker0"])`. Names are case-sensitive and exact.

---

## Optional encrypted discovery (Fernet)

When the server has **`DISCOVERY_ENCRYPTION_ENABLED = True`**, the client must send **Fernet-encrypted** discovery payloads and decrypt **Fernet-encrypted** responses. This hides discovery traffic on the LAN from parties without the key. It does **not** replace TLS for your app: use **HTTPS / WSS** for real application traffic.

**Dependency:** install or upgrade **cryptography** (it is a declared dependency of this package):

```bash
pip install "cryptography>=42.0.0"
```

**Generate a Fernet key** (same key as on the server; never commit it):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Environment variables** (or pass `ClientConfig(encryption_enabled=True, secret_key="...")`):

| Variable | Purpose |
|----------|---------|
| `DISCOVERY_CLIENT_ENCRYPTION_ENABLED` or `DISCOVERY_ENCRYPTION_ENABLED` | Enable Fernet mode (`true` / `1` / `yes` / `on`) |
| `DISCOVERY_CLIENT_SECRET_KEY` or `DISCOVERY_SECRET_KEY` | Same Fernet key string as server `DISCOVERY_SECRET_KEY` |

**Django management command:**

```bash
export DISCOVERY_CLIENT_SECRET_KEY="<your-fernet-key>"
python manage.py discover_servers --encryption
```

The command sets `encryption_enabled`; the secret must come from the environment (or use `load_config()` / `ClientConfig` in code).

---

## Verifying Installation

From the project root (after cloning and installing with the `[network]` extra):

```bash
pip install ".[network]"
python scripts/sanity_check.py
```

The script lists interfaces and broadcast addresses, runs discovery, and prints a table of results or a segmented-network hint if no servers are found.

---

## Logging

Logger name: `django_udp_discovery_client`. Example:

```python
import logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
# Optional: logging.getLogger('django_udp_discovery_client').setLevel(logging.DEBUG)
```

Levels: **DEBUG** (socket/interface detail), **INFO** (discovery start/stop, servers found), **WARNING** (invalid responses, interface issues), **ERROR** (socket/network errors).

---

## Technical Considerations

- **IPv4 only** — No IPv6.
- **UDP broadcast only** — No multicast. Broadcast is limited to the local broadcast domain (often one subnet). Servers on other subnets or VLANs are not discoverable.
- **Blocking API** — `discover()` and `discover_one()` block until timeout; no async API.
- **Segmented / VLAN networks** — On large corporate subnets (e.g. 10.x, 172.16–31.x) segmented into VLANs, broadcast usually reaches only the local segment (e.g. /24). If no servers are found, the management command and `scripts/sanity_check.py` can print a one-time “Segmented Network Detected” message with workarounds:
  - Run client and servers on the same segment.
  - Use direct IP if the server address is known.
  - Involve network admin for broadcast/multicast policy.

---

## Requirements

- Python &gt;= 3.8
- **cryptography** (Fernet), required for the installable package (encrypted and plain discovery).
- **Optional**: `netifaces>=0.11.0` or `ifaddr>=0.2.0` for multi-interface discovery — install with `pip install django-udp-discovery-client[network]`.
- **Optional**: `Django>=3.2` for the management command — install with `pip install django-udp-discovery-client[django]`.

Core library does not require Django. Django is only needed on the server (django-udp-discovery) or for the optional `discover_servers` management command.

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m 'Add some feature'`).
4. Push the branch (`git push origin feature/your-feature`).
5. Open a Pull Request.

Please be respectful and constructive (Code of Conduct).

---

## License

MIT License. See [LICENSE](LICENSE) in the repository root.

---

**Repository:** [https://github.com/Ogro-Projukti/django-udp-discovery-client](https://github.com/Ogro-Projukti/django-udp-discovery-client)
