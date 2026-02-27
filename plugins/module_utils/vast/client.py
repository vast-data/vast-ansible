"""VAST client wrapper around vastpy SDK."""

import sys
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class VastConnection:
    """Connection parameters for VAST VMS."""

    host: str
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    validate_certs: bool = True
    timeout: Optional[int] = None
    tenant: Optional[str] = None
    api_version: Optional[str] = None


class VastClient:
    """Thin wrapper around vastpy VASTClient. Exposes .api for raw access."""

    def __init__(self, connection: VastConnection) -> None:
        if sys.version_info < (3, 9):
            raise RuntimeError("Python 3.9 or later is required. Current: %s" % ".".join(map(str, sys.version_info[:3])))
        try:
            from vastpy import VASTClient as _VASTClient
        except ImportError as e:
            raise RuntimeError("vastpy is required. Install with: pip install vastpy") from e

        kwargs: dict[str, Any] = {
            "address": connection.host,
        }
        if connection.token:
            kwargs["token"] = connection.token
        else:
            kwargs["user"] = connection.username
            kwargs["password"] = connection.password
        if connection.tenant is not None:
            kwargs["tenant"] = connection.tenant
        # Default to 'latest' API version for consistency with other VAST clients
        kwargs["version"] = connection.api_version if connection.api_version is not None else "latest"

        try:
            self._client = _VASTClient(**kwargs)
        except Exception as e:
            raise RuntimeError("Failed to connect to VAST: %s" % e) from e

    @property
    def api(self):
        """Raw vastpy VASTClient for direct API access."""
        return self._client
