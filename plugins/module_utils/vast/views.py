"""View operations using VastClient."""

from typing import Optional

from .client import VastClient
from .errors import VastAPIError


def get_view(client: VastClient, path: str) -> Optional[dict]:
    """
    Get view by path. Returns first match or None.
    Path is the canonical identifier for idempotency.
    VAST API returns a list; we take the first match.
    """
    try:
        views = client.api.views.get(path=path)
    except Exception as e:
        raise VastAPIError("Failed to get view by path %r: %s" % (path, e)) from e
    if not views:
        return None
    # API returns list; path filter should return 0 or 1 items
    return views[0]


def create_view(client: VastClient, payload: dict) -> dict:
    """Create a view. Normalizes create_dir to bool if present."""
    p = dict(payload)
    if "create_dir" in p and p["create_dir"] is not None:
        p["create_dir"] = bool(p["create_dir"])
    try:
        return client.api.views.post(**p)
    except Exception as e:
        raise VastAPIError("Failed to create view: %s" % e) from e


def update_view(client: VastClient, view_id: int, patch: dict) -> dict:
    """Update a view by ID."""
    try:
        return client.api.views[view_id].patch(**patch)
    except Exception as e:
        raise VastAPIError("Failed to update view %s: %s" % (view_id, e)) from e


def delete_view(client: VastClient, view_id: int) -> None:
    """Delete a view by ID."""
    try:
        client.api.views[view_id].delete()
    except Exception as e:
        raise VastAPIError("Failed to delete view %s: %s" % (view_id, e)) from e


def get_policy_id(client: VastClient, policy: str) -> Optional[int]:
    """
    Resolve policy name or ID. Returns policy ID or None if not found.
    If policy looks like an integer, treat as ID directly.
    """
    try:
        pid = int(policy)
        return pid
    except (ValueError, TypeError):
        pass
    try:
        policies = client.api.viewpolicies.get(name=policy)
    except Exception as e:
        raise VastAPIError("Failed to get policy %r: %s" % (policy, e)) from e
    if not policies:
        return None
    # API returns list; name filter should return exactly 1 item
    return policies[0].get("id")
