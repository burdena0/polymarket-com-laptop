"""Authentication for opt-in, read-only LAN status access."""
import base64
import hmac
import ipaddress
from pathlib import Path
import secrets


def password(path=Path('data/monitor-password.txt')):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        try:
            with path.open('x',encoding='utf-8') as stream:stream.write(secrets.token_urlsafe(32))
        except FileExistsError:pass
    value=path.read_text(encoding='utf-8').strip()
    if len(value)<32:raise ValueError('Monitor password invalid')
    return value


def authorized(header, secret, address):
    try:
        ip=ipaddress.ip_address(address)
        if not (ip.is_private or ip.is_loopback):return False
        if not header or not header.startswith('Basic '):return False
        supplied=base64.b64decode(header[6:],validate=True)
        return hmac.compare_digest(supplied,('viewer:'+secret).encode())
    except (ValueError,TypeError):return False
