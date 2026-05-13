# APIs and Limits — Codebase Audit (v1)

**Purpose**: Baseline of all public-facing APIs and known constraints for packaging.  
**Branch**: v1  
**References**: README.md, CHANGELOG.md, docs/internal/info.md

---

## 1. Public-facing API

### 1.1 Main package: `discovery_client`

**Exports** (from `discovery_client/__init__.py` `__all__`):

| Symbol | Type | Description |
|--------|------|-------------|
| `ClientConfig` | Class | Configuration dataclass for discovery (port, message, timeout, interface filters, etc.). |
| `load_config` | Function | Build a `ClientConfig` from env vars and optional kwargs. |
| `DiscoveryResult` | Dataclass | Single discovery result: `ip`, `port`, `raw_response`, `extra`. |
| `discover` | Function | Discover all servers on the local network (blocking). Returns `List[DiscoveryResult]`. |
| `discover_one` | Function | Discover a single server (first found). Returns `Optional[DiscoveryResult]`. |

**Primary entry points**: `discover()` and `discover_one()`.

---

### 1.2 Configuration: `ClientConfig`

- **Module**: `discovery_client.config`
- **Creation**: `ClientConfig(...)` or `ClientConfig.from_env(**overrides)` or `load_config(**kwargs)`.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `discovery_port` | int | 9999 | UDP port for discovery. |
| `discovery_message` | bytes | b"DISCOVER_SERVER" | Message sent in discovery request. |
| `response_prefix` | bytes | b"SERVER_IP:" | Expected prefix in server responses. |
| `timeout` | float | 5.0 | Socket/receive timeout (seconds). |
| `retries` | int | 3 | **Not used in discovery flow** (reserved). |
| `enable_subnet_scan` | bool | True | **Not used in discovery flow** (reserved). |
| `interfaces_whitelist` | Optional[List[str]] | None | If set, only these interface names are used. |
| `interfaces_blacklist` | Optional[List[str]] | None | If set, these interface names are excluded. |

**Methods**:

- `ClientConfig.from_env(**overrides) -> ClientConfig` — Build from env vars; `**overrides` take precedence.

**Environment variables** (prefix `DISCOVERY_CLIENT_`):  
`PORT`, `MESSAGE`, `RESPONSE_PREFIX`, `TIMEOUT`, `RETRIES`, `ENABLE_SUBNET_SCAN`, `INTERFACES_WHITELIST`, `INTERFACES_BLACKLIST`.

---

### 1.3 Result: `DiscoveryResult`

- **Module**: `discovery_client.results`
- **Attributes**: `ip` (str), `port` (int), `raw_response` (bytes), `extra` (optional dict).
- **Validation**: Non-empty `ip`, port 1–65535, `raw_response` must be bytes.

---

### 1.4 Discovery functions

- **`discover(config: Optional[ClientConfig] = None) -> List[DiscoveryResult]`**  
  - Uses multi-interface broadcast; selects interfaces from config (whitelist/blacklist).  
  - Sends discovery message to each selected interface's broadcast address.  
  - Receives until `config.timeout`; parses responses with `config.response_prefix`; deduplicates by `(ip, port)`.  
  - On `OSError`, `ImportError`, or other exception: logs and returns `[]` (does not raise).

- **`discover_one(config: Optional[ClientConfig] = None) -> Optional[DiscoveryResult]`**  
  - Calls `discover(config)` and returns the first result or `None`.

---

### 1.5 Network module: `discovery_client.network`

**Exports** (from `discovery_client/network/__init__.py`):

| Symbol | Type | Description |
|--------|------|-------------|
| `get_interfaces` | Function | List active IPv4 interfaces as `InterfaceInfo`. Requires `netifaces` or `ifaddr`. |
| `select_interfaces` | Function | Filter interfaces using `ClientConfig` whitelist/blacklist. |
| `InterfaceInfo` | Dataclass | `name`, `ip`, `netmask`, `broadcast` (all strings; `broadcast` optional). |
| `netmask_to_prefix` | Function | Netmask string → CIDR prefix (int). |
| `prefix_to_netmask` | Function | CIDR prefix (int) → netmask string. |
| `network_from_ip_and_mask` | Function | Build `ipaddress.IPv4Network` from IP and mask. |
| `broadcast_from_ip_and_mask` | Function | Compute broadcast address from IP and mask. |

**Note**: `discovery_client.network.socket` is used internally by `discover()` (e.g. `discover_servers_single_broadcast`, `discover_servers_multi_interface`). These are not part of the package `__all__` but are importable; treat them as internal for packaging.

---

### 1.6 Django integration: `discovery_client_django`

- **App**: Add `discovery_client_django` to `INSTALLED_APPS` to get the management command.
- **Command**: `python manage.py discover_servers`  
  - **Class**: `discovery_client_django.management.commands.discover_servers.Command`  
  - **Options**: `--timeout`, `--port`, `--message`, `--response-prefix`, `--interfaces-whitelist`, `--interfaces-blacklist`, `--verbose`.  
  - Calls `discover(config)` and prints a table of `DiscoveryResult` (IP, port, URL or raw response).

---

## 2. Known limitations

### 2.1 Protocol and transport

- **IPv4 only**: Sockets use `AF_INET`; response parsing expects dotted-decimal IPv4; `InterfaceInfo` is IPv4. No IPv6.
- **UDP broadcast only**: No multicast. Discovery sends to each interface's broadcast address (or `255.255.255.255` for single-broadcast path).
- **No cross-subnet broadcast**: Broadcast is limited to the local broadcast domain (typically one subnet). Servers on other subnets/VLANs are not discovered unless they are in the same broadcast domain.

### 2.2 Segmented / corporate networks

- **Large subnets (prefix < 24)**: On corporate-style ranges (e.g. 10.x, 172.16–31.x), the code may log a "Segmented Network Detected" warning when **no** servers are found. It does not change behavior; it only warns that broadcast might not reach other segments.
- **No subnet scanning**: There is no iterative scan over a subnet; only broadcast is used. The `enable_subnet_scan` config option is unused.

### 2.3 Blocking vs non-blocking

- **Blocking**: `discover()` and `discover_one()` are blocking. They send broadcasts and then call `recvfrom()` in a loop until the configured `timeout` is reached.
- **No async API**: No `async discover()` or callback-based API.

### 2.4 Retries and robustness

- **Retries not used**: `ClientConfig.retries` is validated and loadable from env but is **not** used in the discovery flow. Each `discover()` call is effectively a single attempt (one send per interface, one receive phase).

### 2.5 Dependencies and platform

- **Optional network stack**: Multi-interface discovery and `get_interfaces()` require either `netifaces` or `ifaddr`. Without them, discovery raises `ImportError` (caught by `discover()`, which then returns `[]` and logs).
- **Django optional**: Core discovery does not require Django. Django is only needed for the `discover_servers` management command.

### 2.6 Response parsing

- **Default port**: If the server response omits the port (e.g. `SERVER_IP:192.168.1.1`), the client assumes port **8000** (hardcoded in `parse_response` in `discovery_client/network/socket.py`).
- **Format**: Expected response format is `<response_prefix><ip>[:<port>]` (e.g. `SERVER_IP:192.168.1.1:8000`). Only IPv4 dotted-decimal is validated.

---

## 3. Hardcoded and default configuration

| Location | Value | Notes |
|----------|--------|--------|
| `discovery_client/network/socket.py` | `DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"` | Used when a single broadcast address is used (e.g. single-broadcast path). |
| `discovery_client/network/socket.py` (parse_response) | Default port `8000` | Used when response has no `:port` part. |
| `discovery_client/config.py` | Port 9999, message `DISCOVER_SERVER`, prefix `SERVER_IP:` | Defaults; overridable via constructor, env, or `load_config()`. |
| `discovery_client_django/management/commands/discover_servers.py` | Same defaults (9999, DISCOVER_SERVER, SERVER_IP:) | For CLI; overridable via arguments. |
| Logging | Logger name `django_udp_discovery_client` | Fixed in code. |

**No environment-specific or absolute file paths** were found in discovery or config code; configuration is via env vars and in-memory config.

---

## 4. Summary table: public API surface

| API | Module | Public | Notes |
|-----|--------|--------|--------|
| `discover` | discovery_client | Yes | Main entry; blocking. |
| `discover_one` | discovery_client | Yes | Wrapper over `discover`. |
| `ClientConfig` | discovery_client | Yes | Config + `from_env()`. |
| `load_config` | discovery_client | Yes | Preferred way to get config. |
| `DiscoveryResult` | discovery_client | Yes | Result dataclass. |
| `get_interfaces` | discovery_client.network | Yes | Requires netifaces or ifaddr. |
| `select_interfaces` | discovery_client.network | Yes | Uses ClientConfig filters. |
| `InterfaceInfo` | discovery_client.network | Yes | Interface dataclass. |
| `netmask_to_prefix`, `prefix_to_netmask` | discovery_client.network | Yes | Utility. |
| `network_from_ip_and_mask`, `broadcast_from_ip_and_mask` | discovery_client.network | Yes | Utility. |
| `discover_servers` (management command) | discovery_client_django | Yes | Django only. |

---

## 5. Acceptance checklist

- [x] All .py files with discovery logic scanned (v1).
- [x] Primary classes/methods listed (DiscoveryClient not present; main API is `discover` / `discover_one` + `ClientConfig` + `DiscoveryResult` + network helpers).
- [x] Limitations documented (IPv4 only, no cross-subnet broadcast, blocking, retries/enable_subnet_scan unused, default port 8000, optional netifaces/ifaddr).
- [x] Hardcoded/default configuration and logger name documented; no env-specific paths.
- [x] APIS_AND_LIMITS.md aligned with README, CHANGELOG, and info.md.
