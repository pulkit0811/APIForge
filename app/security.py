import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    pass


def validate_url_syntax(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https and include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"} or parsed.hostname.lower().endswith(".local"):
        raise ValueError("Local hostnames are not allowed")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid port") from exc
    return value.strip()


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local


def validate_public_destination(url: str) -> str:
    value = validate_url_syntax(url)
    hostname = urlsplit(value).hostname
    if hostname is None:
        raise UnsafeUrlError("URL has no hostname")
    try:
        if _is_blocked_ip(hostname):
            raise UnsafeUrlError("Private, loopback, link-local, or reserved destinations are blocked")
    except ValueError:
        try:
            addresses = {result[4][0] for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise UnsafeUrlError("Could not resolve the destination hostname") from exc
        if not addresses or any(_is_blocked_ip(address) for address in addresses):
            raise UnsafeUrlError("Private, loopback, link-local, or reserved destinations are blocked")
    return value
