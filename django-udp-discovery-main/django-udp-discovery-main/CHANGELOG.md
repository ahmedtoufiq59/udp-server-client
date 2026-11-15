# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-15

### Added

- Optional Fernet-encrypted discovery: `DISCOVERY_ENCRYPTION_ENABLED`, `DISCOVERY_SECRET_KEY` (setting or environment variable).
- Encrypted requests expire: `DISCOVERY_ENCRYPTION_TTL` (default 30 s) with `DISCOVERY_ENCRYPTION_CLOCK_SKEW` (default 10 s) tolerance.
- Replay protection: each encrypted request is answered at most once (`DISCOVERY_REPLAY_CACHE_SIZE`, default 10000).
- The client nonce in `DISCOVER_SERVER|<nonce>` is echoed in the encrypted reply (`SERVER_IP:<ip>|<nonce>`).
- Key rotation: `DISCOVERY_PREVIOUS_SECRET_KEYS` are accepted for decryption; replies always use `DISCOVERY_SECRET_KEY`.
- `DISCOVERY_AUTOSTART` setting (default `True`) to turn off starting the listener when Django loads.
- `start_discovery` shows whether encryption is enabled.

### Changed

- The listener auto-starts only where it is useful: in `runserver`'s serving process (not the auto-reloader parent) and in non-management processes such as gunicorn or uvicorn. Other `manage.py` commands (`migrate`, `shell`, `start_discovery`, ...) no longer start it.
- When the port is already taken, the listener logs one error line instead of a traceback.
- `start_discovery` no longer suggests the non-existent `test_client.py` script or `test_discovery` command.

### Compatibility

- Plain mode is unchanged. Encrypted servers still answer older encrypted clients that send no nonce.
- Clients from django-udp-discovery-client 1.1.0 require the nonce echo, so upgrade servers first, or together with clients.

## [1.0.0]

- Initial release: background UDP listener, `start_discovery` command, configurable port, message and response prefix.
