# Codebase overview

Directory tree (one line per node) and short description for every file and folder.

---

## Directory tree

```
django-udp-discovery-client/
discovery_client/
discovery_client/__init__.py
discovery_client/config.py
discovery_client/network/
discovery_client/network/__init__.py
discovery_client/network/interfaces.py
discovery_client/network/socket.py
discovery_client/network/utils.py
discovery_client/py.typed
discovery_client/results.py
discovery_client_django/
discovery_client_django/__init__.py
discovery_client_django/apps.py
discovery_client_django/management/
discovery_client_django/management/__init__.py
discovery_client_django/management/commands/
discovery_client_django/management/commands/__init__.py
discovery_client_django/management/commands/discover_servers.py
docs/
docs/internal/
docs/internal/APIS_AND_LIMITS.md
docs/internal/info.md
scripts/
scripts/sanity_check.py
tests/
tests/test_config.py
tests/test_discovery_api.py
tests/test_integration.py
tests/test_interface_filtering.py
tests/test_logging_and_errors.py
tests/test_multi_interface_discovery.py
tests/test_network.py
tests/test_network_utils.py
tests/test_udp_discovery.py
CHANGELOG.md
LICENSE
MANIFEST.in
pyproject.toml
README.md
test_current_capabilities.py
```

---

## Files and folders

| Path | Description |
|------|-------------|
| **django-udp-discovery-client/** | Repository root: Django UDP discovery client library and optional Django app. |
| **discovery_client/** | Main Python package: UDP discovery client (no Django required). |
| discovery_client/__init__.py | Package root; exports discover, discover_one, ClientConfig, load_config, DiscoveryResult. |
| discovery_client/config.py | ClientConfig dataclass and load_config(); env vars (DISCOVERY_CLIENT_*) and validation. |
| **discovery_client/network/** | Network helpers: interfaces, socket ops, netmask/utils. |
| discovery_client/network/__init__.py | Re-exports get_interfaces, select_interfaces, InterfaceInfo, netmask/prefix and broadcast utils. |
| discovery_client/network/interfaces.py | get_interfaces(), select_interfaces(); InterfaceInfo; uses netifaces or ifaddr. |
| discovery_client/network/socket.py | UDP discovery: parse_response, create_discovery_socket, send/receive, discover_servers_*; detect_segmented_network, format_segmented_network_warning. |
| discovery_client/network/utils.py | netmask_to_prefix, prefix_to_netmask, network_from_ip_and_mask, broadcast_from_ip_and_mask. |
| discovery_client/py.typed | PEP 561 marker for type-checked package. |
| discovery_client/results.py | DiscoveryResult dataclass (ip, port, raw_response, extra). |
| **discovery_client_django/** | Optional Django app: management command for discovery. |
| discovery_client_django/__init__.py | Package init. |
| discovery_client_django/apps.py | AppConfig for discovery_client_django. |
| **discovery_client_django/management/** | Django management package. |
| discovery_client_django/management/__init__.py | Management package init. |
| **discovery_client_django/management/commands/** | Management commands. |
| discovery_client_django/management/commands/__init__.py | Commands package init. |
| discovery_client_django/management/commands/discover_servers.py | Management command: python manage.py discover_servers; prints table and segmented-network diagnostic once if no results. |
| **docs/** | Documentation (not shipped in sdist). |
| **docs/internal/** | Internal docs (APIs, limits, package info). |
| docs/internal/APIS_AND_LIMITS.md | Public API list and known limitations (audit baseline). |
| docs/internal/info.md | Package capabilities and API reference. |
| **scripts/** | Standalone scripts (e.g. sanity check). |
| scripts/sanity_check.py | Post-install sanity check: list interfaces/broadcasts, run discover(), print results or segmented-network diagnostic once. |
| **tests/** | Pytest suite for discovery_client and behavior. |
| tests/test_config.py | load_config() env vs defaults vs kwargs priority. |
| tests/test_discovery_api.py | discover, discover_one, DiscoveryResult, imports. |
| tests/test_integration.py | Integration tests with mock UDP server. |
| tests/test_interface_filtering.py | Whitelist/blacklist and select_interfaces. |
| tests/test_logging_and_errors.py | Logging and error paths in socket/discovery. |
| tests/test_multi_interface_discovery.py | Multi-interface discovery and deduplication. |
| tests/test_network.py | discover() with no interfaces or ImportError; sanity_check prints "Segmented Network Detected" exactly once (capsys). |
| tests/test_network_utils.py | netmask_to_prefix, prefix_to_netmask, network_from_ip_and_mask, broadcast_from_ip_and_mask. |
| tests/test_udp_discovery.py | parse_response, receive_responses, discover_servers_single_broadcast, socket behavior. |
| CHANGELOG.md | Version history and notable changes. |
| LICENSE | MIT license text. |
| MANIFEST.in | sdist include/prune: metadata + discovery_client* + discovery_client_django*; prune audit, dev_test, docs, tests. |
| pyproject.toml | Build (setuptools), project metadata, optional deps (network, django, dev, test), package find. |
| README.md | User-facing docs: install, usage, limitations, verifying installation, sanity_check. |
| test_current_capabilities.py | Ad-hoc script to exercise config/interfaces (not part of pytest). |
