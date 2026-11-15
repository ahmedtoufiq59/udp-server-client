# udp server client

Zero-configuration server discovery for Django on a local network, with optional Fernet-encrypted discovery.

| Folder | What it is |
|--------|------------|
| `django-udp-discovery-main/django-udp-discovery-main/` | **Server** package `django-udp-discovery` (Django app that answers UDP discovery broadcasts) |
| `django-udp-discovery-client-main/django-udp-discovery-client-main/` | **Client** package `django-udp-discovery-client` (finds servers; optional Django `discover_servers` command) |
| `demo/` | Django project wired up with the server (and the client command, when installed) |
| `PITCH.md` | Design overview and security model |

Each package has its own README and CHANGELOG with the full settings reference.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -e django-udp-discovery-main/django-udp-discovery-main \
            -e "django-udp-discovery-client-main/django-udp-discovery-client-main[network]"
```

### Run the demo server (encrypted, the default)

```bash
export DISCOVERY_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
cd demo
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

The UDP listener starts with `runserver` on port 9999. To run the demo without encryption, set `DISCOVERY_ENCRYPTION_ENABLED=false` instead of a key.

### Find it from a client

In another terminal, with the same key exported:

```bash
cd demo
python manage.py discover_servers --encryption
```

Or from plain Python:

```python
import os
from discovery_client import ClientConfig, discover

print(discover(ClientConfig(encryption_enabled=True, secret_key=os.environ["DISCOVERY_SECRET_KEY"])))
```

Leave out `--encryption` / `encryption_enabled` when the server runs in plain mode.

## Running the tests

```bash
# Server (from the demo project, using its test settings)
cd demo
python manage.py test django_udp_discovery --settings=demo.test_settings

# Client
cd django-udp-discovery-client-main/django-udp-discovery-client-main
pip install pytest
pytest tests
```
