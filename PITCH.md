# CodeWizardry UDP Discovery: Zero-Configuration Encrypted Service Discovery for Offline LAN-Based Django Systems

**Workspace:** `udp server client`  
**Packages:** `django-udp-discovery` (teacher/server) · `django-udp-discovery-client` (student/client)

---

## 1. Executive Summary

In many university labs and offline intranets, a **teacher** runs a Django application on one machine while **students** connect from laptops or lab PCs. There is often no reliable DNS, no public internet, and the server’s IP address changes when DHCP renews or when equipment is moved.

This workspace implements a **dual-package UDP discovery system** that solves that problem:

- The **teacher/server** installs **django-udp-discovery**, which listens on the LAN for a small, well-known discovery message and replies with the server’s IP address.
- **Students/clients** use **django-udp-discovery-client** to broadcast a discovery request, collect responses, and obtain the server address **without typing an IP manually**.
- Discovery works on a **local area network (LAN) or intranet** with no cloud dependency.
- An optional **Fernet-based authenticated encrypted discovery phase** protects discovery packets so only parties that share a pre-configured secret can complete discovery—while keeping **plain UDP mode** available for backward compatibility.

After discovery, applications connect using normal **HTTP/HTTPS** or **WebSocket/WSS**; securing that application traffic remains the responsibility of TLS on the app layer, not UDP discovery alone.

---

## 2. Problem Statement

Offline and semi-offline teaching environments create recurring connectivity problems:

| Challenge | Impact |
|-----------|--------|
| No DNS or internet on the lab VLAN | Students cannot resolve a hostname |
| DHCP and roaming devices | Server IP changes between sessions |
| Manual IP handout | Slow, error-prone, support-heavy |
| Wrong subnet or typo | Connection failures and lost lab time |
| Curious peers on the same LAN | Plain discovery reveals “where is the teacher server?” to anyone listening |

Traditional fixes—whiteboards, printed IPs, static DHCP reservations, or mDNS daemons—are brittle, platform-specific, or require extra infrastructure. What is needed is a **lightweight, Django-native discovery layer** that works where Django already runs, with an **optional** way to authenticate discovery traffic without claiming full application encryption.

---

## 3. Proposed Solution

The solution is split into two cooperating Python packages in this repository:

| Package | Role | Location in workspace |
|---------|------|------------------------|
| **django-udp-discovery** | Teacher/server Django app: background UDP listener, validates requests, responds with IP | `django-udp-discovery-main/django-udp-discovery-main/` |
| **django-udp-discovery-client** | Student/client library: broadcast discovery, parse responses, optional Django CLI | `django-udp-discovery-client-main/django-udp-discovery-client-main/` |

**Core mechanism**

1. Client sends a **UDP broadcast** (default port **9999**) with payload **`DISCOVER_SERVER`** (configurable).
2. Server **validates** the message against `DISCOVERY_MESSAGE`.
3. Server replies with **`SERVER_IP:<address>`** (configurable prefix); client may parse an optional **`:port`** in the response (default application port **8000** if omitted).
4. Client builds a connection URL (e.g. `http://<ip>:<port>`) and the main Django app takes over.

**Optional authenticated encrypted discovery phase**

- When **`DISCOVERY_ENCRYPTION_ENABLED=True`** on the server and matching settings on the client, payloads are **Fernet tokens** (from the `cryptography` library).
- The server **decrypts**, validates plaintext equals `DISCOVERY_MESSAGE`, then **encrypts** the response.
- The client **encrypts** the request and **decrypts** the response before parsing.
- **Invalid tokens are ignored**; the listener does not crash on malformed UDP traffic.

---

## 4. System Architecture

### 4.1 Components

**Server (`django_udp_discovery`)**

| Module | Responsibility |
|--------|----------------|
| `apps.py` | Starts UDP listener when Django loads (skipped in tests) |
| `listener.py` | Threaded UDP socket, bind `0.0.0.0:DISCOVERY_PORT`, receive loop |
| `conf.py` | Settings wrapper with defaults and Django `settings.py` overrides |
| `crypto.py` | Resolve `DISCOVERY_SECRET_KEY`, validate Fernet key, encrypt/decrypt bytes |
| `utility.py` | Server IP detection, port helpers |
| `management/commands/start_discovery.py` | Manual start/stop/duration control |

**Client (`discovery_client`)**

| Module | Responsibility |
|--------|----------------|
| `config.py` | `ClientConfig`, `load_config()`, env vars `DISCOVERY_CLIENT_*` |
| `crypto_util.py` | Fernet helpers for client-side encrypt/decrypt |
| `network/socket.py` | Broadcast send, receive loop, `parse_response()`, multi-interface discovery |
| `network/interfaces.py` | Interface selection (whitelist/blacklist; needs `[network]` extra) |
| `results.py` | `DiscoveryResult` (ip, port, raw_response, extra) |
| `discovery_client_django` | Optional `discover_servers` management command |

### 4.2 ASCII architecture diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OFFLINE LAN / INTRANET (same broadcast domain)        │
└─────────────────────────────────────────────────────────────────────────────┘

  STUDENT / CLIENT DEVICE                         TEACHER / SERVER (Django)
 ┌──────────────────────────┐                   ┌──────────────────────────┐
 │ django-udp-discovery-    │                   │ django-udp-discovery     │
 │ client                   │                   │ (INSTALLED_APPS)         │
 │                          │                   │                          │
 │  discover() /            │    UDP :9999      │  listener.py (thread)    │
 │  discover_servers        │ ─── broadcast ──► │  bind 0.0.0.0:9999       │
 │                          │ ◄── unicast ───── │  validate + respond      │
 │  network/socket.py       │                   │  crypto.py (optional)    │
 └────────────┬─────────────┘                   └────────────┬─────────────┘
              │                                              │
              │  DiscoveryResult: ip, port                     │  get_server_ip()
              ▼                                              ▼
 ┌──────────────────────────┐                   ┌──────────────────────────┐
 │ Application layer        │                   │ Django app (runserver,   │
 │ HTTP / HTTPS             │ ◄═════ LAN ═════► │  ASGI, REST, websockets) │
 │ WebSocket / WSS          │   (NOT UDP disc.) │                          │
 └──────────────────────────┘                   └──────────────────────────┘

  Plain mode:     DISCOVER_SERVER  ──►  SERVER_IP:192.168.x.x[:port]
  Encrypted mode: Fernet(DISCOVER_SERVER) ──► Fernet(SERVER_IP:...)
```

### 4.3 Phases of communication

| Phase | Protocol | Security |
|-------|----------|----------|
| **Discovery** | UDP broadcast + unicast reply | Optional Fernet (authenticated encryption for discovery packets only) |
| **Application** | HTTP(S), WebSocket(S) | Use **HTTPS / WSS** (or equivalent) for production confidentiality and integrity |

---

## 5. Discovery Workflow

### 5.1 Plain mode (default, backward compatible)

`DISCOVERY_ENCRYPTION_ENABLED=False` on server; `encryption_enabled=False` on client.

```
Client                          Server (listener thread)
  |                                    |
  |  UDP broadcast                     |
  |  "DISCOVER_SERVER"  ------------>  |  recvfrom()
  |                                    |  data == DISCOVERY_MESSAGE ?
  |                                    |  yes: build SERVER_IP:<ip>
  |  <-------------------------------  |  sendto() to client address
  |  "SERVER_IP:10.0.0.5"              |
  |                                    |
  |  parse_response() -> ip, port      |
  |  connect http://10.0.0.5:8000      |
  v                                    v
```

### 5.2 Encrypted mode (authenticated encrypted discovery phase)

Both sides share the same **`DISCOVERY_SECRET_KEY`** (Fernet key). Server has **`DISCOVERY_ENCRYPTION_ENABLED=True`**; client sets **`encryption_enabled=True`** (or env / `--encryption`).

```
Client                          Server
  |                                    |
  |  Fernet.encrypt(b"DISCOVER_SERVER")|
  |  ------------------------------->  |  decrypt_bytes()
  |                                    |  InvalidToken -> ignore (no crash)
  |                                    |  plaintext == DISCOVERY_MESSAGE ?
  |                                    |  encrypt(SERVER_IP:<ip>)
  |  <-------------------------------  |
  |  Fernet token (ciphertext)         |
  |                                    |
  |  decrypt -> parse SERVER_IP:...    |
  |  connect (prefer HTTPS/WSS next)   |
  v                                    v
```

**Rejection rules in encrypted mode**

- Plaintext `DISCOVER_SERVER` on the wire → **ignored** (no response).
- Garbage UDP → **ignored**.
- Fernet token with **wrong key** → **ignored**.
- Fernet token with **wrong inner message** → **ignored**.

---

## 6. Security Design

### 6.1 What Fernet provides here

[Fernet](https://cryptography.io/en/latest/fernet/) (via `cryptography.fernet`) gives **symmetric authenticated encryption**: confidentiality and integrity for the discovery payload, with **InvalidToken** on tampering or wrong keys. This is referred to throughout the project as an **authenticated encrypted discovery phase**, not end-to-end encryption of the entire system.

### 6.2 Key management

- Generate once per deployment or lab session:  
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- **Server:** `DISCOVERY_SECRET_KEY` in Django `settings.py` or environment variable (see `django_udp_discovery.crypto.resolve_discovery_secret_key_string`).
- **Client:** `DISCOVERY_CLIENT_SECRET_KEY` or `DISCOVERY_SECRET_KEY` (must match server).
- **Never** commit production keys to Git; distribute via secure channel (USB policy file, lab image, secrets manager).

### 6.3 Threat model (honest scope)

| Protected | Not protected by discovery encryption alone |
|-----------|---------------------------------------------|
| Discovery request/response content on the LAN from parties without the key | HTTP API bodies, cookies, sessions after connect |
| Casual sniffing of “who is the teacher server?” in encrypted mode | Traffic on other subnets (broadcast does not cross routers) |
| Accidental wrong-key clients (they get no usable reply) | Insider with the shared key (they can discover) |

**After discovery**, use **HTTPS** and **WSS** for application data. UDP discovery does not replace TLS.

### 6.4 Safe failure behavior

- **`InvalidToken`** and malformed packets: handled without terminating the listener thread.
- Misconfiguration (encryption on, missing/invalid key): server listener **fails to start** with a logged error rather than falling back to silent insecure mode.

---

## 7. Key Features

- **Zero-configuration discovery** — Sensible defaults; server auto-starts with Django.
- **Offline LAN / intranet** — No cloud, no DNS required for discovery.
- **Pure Python / Django integration** — Server is a Django app; client core has no Django dependency.
- **Optional authenticated encrypted discovery** — Fernet when both sides enable it.
- **Backward compatibility** — Plain UDP unchanged when encryption flags are off.
- **Multi-interface discovery (client)** — Broadcast per interface, deduplicate by `(ip, port)` with `[network]` extra (`netifaces` / `ifaddr`).
- **Safe invalid packet handling** — Ignore bad decrypts and wrong messages; no listener crash.
- **Management commands** — `start_discovery` (server), `discover_servers` (client, optional `--encryption`).
- **Test coverage** — Django tests (server), pytest (client), including encrypted round-trips and negative cases.
- **Configurable protocol** — Port, message, response prefix, timeouts, interface filters.

**Platform note:** Server package documents **Windows and Linux** support; **macOS is not supported** for the server listener. The **client** supports Windows, Linux, and macOS.

---

## 8. Configuration Guide

### 8.1 Server (Django `settings.py`)

```python
INSTALLED_APPS = [
    # ...
    "django_udp_discovery",
]

# Optional — defaults shown
DISCOVERY_PORT = 9999
DISCOVERY_MESSAGE = "DISCOVER_SERVER"
RESPONSE_PREFIX = "SERVER_IP:"

# Encrypted discovery (optional)
DISCOVERY_ENCRYPTION_ENABLED = True
DISCOVERY_SECRET_KEY = "<paste-fernet-key-here>"  # never commit real keys
```

Environment alternative for the secret (when not set in Django settings): **`DISCOVERY_SECRET_KEY`**.

### 8.2 Client (environment or code)

```bash
# Recommended for multi-interface labs
pip install "django-udp-discovery-client[network]"
pip install "cryptography>=42.0.0"
```

```bash
export DISCOVERY_CLIENT_PORT=9999
export DISCOVERY_CLIENT_TIMEOUT=5.0

# Encrypted discovery (must match server)
export DISCOVERY_ENCRYPTION_ENABLED=True
# or: export DISCOVERY_CLIENT_ENCRYPTION_ENABLED=True
export DISCOVERY_SECRET_KEY="<same-fernet-key-as-server>"
# or: export DISCOVERY_CLIENT_SECRET_KEY="<same-fernet-key-as-server>"
```

```python
from discovery_client import ClientConfig, discover

config = ClientConfig(
    encryption_enabled=True,
    secret_key="<same-fernet-key-as-server>",
    timeout=5.0,
)
servers = discover(config=config)
```

### 8.3 Generate Fernet key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 9. How to Run

Paths below assume development layout inside this workspace. Adjust `cd` to your clone root.

### 9.1 Install dependencies

**Server (teacher machine)**

```bash
cd django-udp-discovery-main/django-udp-discovery-main
pip install -e .
# cryptography is a declared dependency of django-udp-discovery
```

**Client (student machines)**

```bash
cd django-udp-discovery-client-main/django-udp-discovery-client-main
pip install -e ".[network]"   # recommended: multi-interface discovery
```

### 9.2 Encryption disabled (plain mode)

**Server:** Add `django_udp_discovery` to `INSTALLED_APPS` and run Django as usual. Discovery starts automatically. Optional manual control:

```bash
python manage.py start_discovery
```

**Client (Python)**

```python
from discovery_client import discover, discover_one

for server in discover():
    print(f"http://{server.ip}:{server.port}")
```

**Client (optional Django command)**

```bash
python manage.py discover_servers --timeout 5.0 --port 9999 --verbose
```

### 9.3 Encryption enabled

**Server `settings.py`**

```python
DISCOVERY_ENCRYPTION_ENABLED = True
DISCOVERY_SECRET_KEY = "<shared-fernet-key>"
```

**Client**

```bash
export DISCOVERY_SECRET_KEY="<shared-fernet-key>"
export DISCOVERY_ENCRYPTION_ENABLED=True
python manage.py discover_servers --encryption --verbose
```

Or in Python:

```python
from discovery_client import load_config, discover

config = load_config(encryption_enabled=True)  # key from env
servers = discover(config=config)
```

**Sanity check script (client repo)**

```bash
cd django-udp-discovery-client-main/django-udp-discovery-client-main
pip install ".[network]"
python scripts/sanity_check.py
```

---

## 10. Testing and Validation

### 10.1 Server (`django_udp_discovery.tests`)

Run from a Django project that includes the app, or from `src/` with test settings:

```bash
cd django-udp-discovery-main/django-udp-discovery-main/src
python -m django test django_udp_discovery.tests
```

| Scenario | Expected behavior |
|----------|-------------------|
| Plain valid `DISCOVER_SERVER` | Plain `SERVER_IP:...` response |
| Encrypted round-trip (same key) | Encrypted reply; decrypts to `SERVER_IP:...` |
| Plaintext client when server encryption on | **No response** |
| Garbage / invalid Fernet on wire | **Ignored**; listener stays up |
| Fernet with **wrong key** | **No response** |
| Fernet decrypt OK but **wrong inner message** | **No response** |
| Encryption on, **missing/invalid secret** | Listener does not stay running |
| `DiscoveryCryptoUtilityTest` | Key resolution, encrypt/decrypt, no secret in error strings |

### 10.2 Client (`tests/`, pytest)

```bash
cd django-udp-discovery-client-main/django-udp-discovery-client-main
pip install -e . pytest cryptography
python -m pytest tests/ -q
```

| Scenario | Coverage |
|----------|----------|
| `_outgoing_discovery_payload` | Fernet ciphertext for discovery message |
| `receive_responses` encrypted | Decrypt then parse; invalid token skipped |
| Plain mode | Unchanged wire format and `raw_response` |
| `load_config` / env | `DISCOVERY_CLIENT_*`, `DISCOVERY_ENCRYPTION_ENABLED`, `DISCOVERY_SECRET_KEY` |
| Mocked discovery flow | Send path uses encrypted payload when enabled |

---

## 11. Use Cases

- **Offline university classrooms** — Teacher laptop as Django server; students auto-find IP.
- **Computer lab exams** — Controlled VLAN; optional encrypted discovery reduces casual snooping.
- **Intranet training** — Corporate or campus networks without public DNS for lab apps.
- **Air-gapped research** — Isolated networks where mDNS or cloud registry is unavailable.
- **Local CodeWizardry / workshop demos** — Fast setup without editing IPs on every machine.
- **IoT / edge gateways on LAN** — Discover a Django edge controller from a tooling script.
- **Rural or low-infrastructure sites** — Minimal moving parts: Python, Django, UDP, optional shared key.

---

## 12. Limitations

| Limitation | Detail |
|------------|--------|
| **Broadcast scope** | UDP broadcast typically reaches only the **same broadcast domain** (often one /24 subnet). Servers on other VLANs are not discovered without relays or scanning extensions. |
| **IPv4 focus** | Discovery is designed around IPv4 LANs; no IPv6 discovery in current design. |
| **Shared secret distribution** | Fernet mode requires **out-of-band** secure distribution of `DISCOVERY_SECRET_KEY`; it is not a public-key infrastructure. |
| **Not full app security** | Discovery encryption does **not** secure HTTP APIs, admin panels, or websockets—use **HTTPS/WSS** after connect. |
| **Firewall / AP isolation** | Client isolation on Wi‑Fi or strict UDP rules can block broadcast or replies. |
| **Server OS** | Server package targets **Windows/Linux**; not supported on macOS for the listener. |
| **Segmented corporate networks** | Large subnets may be VLAN-segmented; client may print segmented-network guidance when no servers are found. |

---

## 13. Future Improvements

- **First-class HTTPS/WSS documentation and helpers** — Post-discovery URL builder with TLS hints and certificate pinning options.
- **Key rotation** — Support multiple valid Fernet keys during rotation windows.
- **Public-key discovery** — Encrypt discovery with a server public key; students only need the public half.
- **QR-based key sharing** — Display or scan lab session keys at room entry.
- **Admin dashboard** — Live view of discovery requests, encryption mode, and connected subnets.
- **Rich service metadata** — Version, role (teacher/student), capabilities in encrypted JSON inside discovery response.
- **Multi-server selection** — UI or API when several teachers respond on the same LAN.
- **Subnet relay / directed unicast** — Reach adjacent segments without full subnet scanning.
- **Comparison benchmarks** — Formal evaluation vs mDNS, SSDP, and custom scanning in paper experiments.

---

## 14. Research and Paper Relevance

This system addresses an **infrastructure-independent service discovery** problem for **offline Django deployments**:

1. **Problem framing** — Dynamic IPs and absent DNS in lab VLANs make manual configuration a recurring failure mode; quantify time lost and error rates vs automated discovery.
2. **Design contribution** — Application-layer UDP discovery **embedded in Django** (no Avahi/Bonjour daemon), with an optional **authenticated encrypted discovery phase** using standard Fernet.
3. **Comparative analysis** — Contrast with **mDNS/DNS-SD** (daemon + OS integration), **SSDP/UPnP** (different ecosystem), and **brute-force subnet scan** (noisy, slow, firewall-sensitive).
4. **Security discussion** — Clear separation: discovery confidentiality vs **TLS for application data**; threat model for shared-key LAN labs.
5. **Evaluation metrics** — Discovery latency, success rate across N interfaces, false positives under noise, behavior under wrong keys and malformed packets (supported by existing automated tests).
6. **Reproducibility** — Two open packages, documented defaults (port 9999, message `DISCOVER_SERVER`), test suites for plain and encrypted modes.

Suitable venues: software engineering education, offline-first systems, IoT edge tooling, or applied security (LAN discovery hardening) workshops.

---

## 15. Repository Layout (this workspace)

```
udp server client/
├── PITCH.md                          ← this document
├── README.md
├── django-udp-discovery-main/
│   └── django-udp-discovery-main/
│       ├── pyproject.toml            # package: django-udp-discovery
│       ├── README.md
│       └── src/django_udp_discovery/
│           ├── apps.py
│           ├── conf.py
│           ├── crypto.py
│           ├── listener.py
│           ├── utility.py
│           ├── tests.py
│           └── management/commands/start_discovery.py
└── django-udp-discovery-client-main/
    └── django-udp-discovery-client-main/
        ├── pyproject.toml            # package: django-udp-discovery-client
        ├── README.md
        ├── discovery_client/
        │   ├── __init__.py           # discover(), discover_one(), load_config()
        │   ├── config.py
        │   ├── crypto_util.py
        │   ├── results.py
        │   └── network/
        │       ├── socket.py
        │       └── interfaces.py
        ├── discovery_client_django/
        │   └── management/commands/discover_servers.py
        ├── scripts/sanity_check.py
        └── tests/                    # pytest
```

---

## 16. Short Pitch (presentation closing)

**CodeWizardry UDP Discovery** lets a Django teacher application announce itself on an offline lab network without anyone writing IP addresses on the board. Students run a small Python client—or a single management command—that broadcasts a discovery message; the server answers with its current address, and the class can start working in seconds. When labs need a harder edge against casual network sniffing, both sides flip on **Fernet authenticated encrypted discovery** with one shared secret, while older plain mode keeps working for simple demos. The design stays honest: discovery is only the first handshake—real assignments and APIs still belong on **HTTPS and WSS**. Built as two focused packages with tests for plain traffic, encrypted round-trips, wrong keys, and junk packets, the system is ready for GitHub, classroom deployment, and academic evaluation as a practical answer to offline LAN service discovery for Django.

---

*Document version aligns with implementation in `django-udp-discovery` and `django-udp-discovery-client` as of the Fernet encryption feature. For package-specific install and API detail, see each project’s `README.md`.*
