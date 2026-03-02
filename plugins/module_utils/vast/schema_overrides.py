"""Schema overrides for VAST resources.

This file provides manual overrides for resource field classifications that cannot
be reliably inferred from the Swagger specification. Use this to define:

- read_only_fields: Fields that should be ignored in diff and not sent in payloads
- immutable_fields: Fields that cannot be changed after creation (require recreate)
- ephemeral_fields: Write-only fields never returned by API (passwords, create_dir)
- set_like_lists: List fields where order doesn't matter (compared as sets)
- lookup_field: Canonical identifier for idempotency lookups
- field_normalizers: Functions to normalize field values before comparison (for API transformations)

Note: Fields missing from list endpoints are automatically handled - the system
refetches from detail endpoint when user provides fields not present in list result.

These overrides are consulted by the module generator and at runtime for proper
idempotent behavior.
"""

from typing import Any, Dict, Set


def normalize_list_by_user_schema(api_value: Any, user_value: Any) -> Any:
    """Generic normalizer for list fields that keeps only user-provided keys.

    Args:
        api_value: List value returned by API (may have extra fields in each dict)
        user_value: List value provided by user (defines the schema)

    Returns:
        Normalized list with only user-provided keys, flattening nested 'entity' objects

    Example:
        User provides: [{"identifier": "user1", "hard_limit": 1000}]
        API returns: [{"entity": {"identifier": "user1", "vast_id": 123}, "hard_limit": 1000, "state": "OK"}]
        Returns: [{"identifier": "user1", "hard_limit": 1000}]
    """
    if api_value is None or user_value is None:
        return api_value
    if not isinstance(api_value, list):
        return api_value
    if len(user_value) == 0:
        return api_value

    user_schema = user_value[0]

    normalized = []
    for api_item in api_value:
        normalized_item = {}
        for key in user_schema.keys():
            try:
                if key in api_item:
                    value = api_item[key]
                elif "entity" in api_item and key in api_item["entity"]:
                    entity_value = api_item["entity"][key]
                    # The entity sub-object is the API's read-only view of the
                    # referenced user/group profile. Fields like identifier and
                    # identifier_type are reliably echoed, but others (e.g. email)
                    # may carry different semantics than the flat field the user
                    # sent.  When the entity value disagrees with what the user
                    # provided, the field is unverifiable through GET — treat it
                    # like an ephemeral/write-only field by adopting the user's
                    # value so both sides of the comparison stay consistent.
                    if entity_value != user_schema.get(key):
                        value = user_schema[key]
                    else:
                        value = entity_value
                else:
                    continue

                # Normalize "All" → "" transformation for fqdn fields (share_acl)
                if key == "fqdn" and value == "" and user_schema.get(key) == "All":
                    value = "All"

                if value is not None:
                    normalized_item[key] = value
            except (TypeError, KeyError):
                continue

        normalized.append(normalized_item)

    return normalized


def normalize_dict_by_user_schema(api_value: Any, user_value: Any) -> Any:
    """Generic normalizer for dict fields that keeps only user-provided keys.

    Args:
        api_value: Dict value returned by API (may have extra fields)
        user_value: Dict value provided by user (defines the schema)

    Returns:
        Normalized dict with only user-provided keys

    Example:
        User provides: {"soft_limit": 50000, "hard_limit": 100000}
        API returns: {"soft_limit": 50000, "hard_limit": 100000, "quota_system_id": 152, "grace_period": null}
        Returns: {"soft_limit": 50000, "hard_limit": 100000}
    """
    if api_value is None or user_value is None:
        return api_value
    if not isinstance(api_value, dict) or not isinstance(user_value, dict):
        return api_value

    normalized = {}
    for key in user_value.keys():
        if key in api_value and api_value[key] is not None:
            normalized[key] = api_value[key]

    return normalized


def normalize_share_acl(api_value: Any, user_value: Any) -> Any:
    """Normalize share_acl field (wrapper for nested acl list).

    Args:
        api_value: share_acl dict from API with nested 'acl' list
        user_value: share_acl dict from user with nested 'acl' list

    Returns:
        Normalized share_acl with only user-provided keys in acl entries
    """
    if not user_value or "acl" not in user_value:
        return api_value

    # Normalize the nested 'acl' list using generic list normalizer
    if "acl" in api_value:
        normalized_acl = normalize_list_by_user_schema(api_value["acl"], user_value["acl"])
        return {**api_value, "acl": normalized_acl}

    return api_value


# Resource-specific overrides
OVERRIDES: Dict[str, Dict[str, Any]] = {
    "views": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "title",
            "internal",
            "sync",
            "sync_time",
            "is_remote",
            "directory",
            "physical_capacity",
            "logical_capacity",
            "bulk_permission_update_state",
            "bulk_permission_update_progress",
            "has_bucket_logging_sources",
            "has_bucket_logging_destination",
            "cluster",
            "cluster_id",
            "tenant_name",
            "ignore_oos",
        },
        "immutable_fields": {"path", "tenant_id"},
        "ephemeral_fields": {"create_dir"},
        "set_like_lists": {"protocols", "abac_tags", "abe_protocols"},
        "lookup_field": "path",
        "field_normalizers": {
            "share_acl": normalize_share_acl,  # Generic normalizer handles 'All' → '' and API-added fields
        },
    },
    "users": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "provider_name",
        },
        "immutable_fields": {
            "name",
            "local_provider_id",
        },  # Username cannot be changed, local_provider_id is write-once at creation
        "ephemeral_fields": {
            "password",  # Never returned by API; only sent on create (excluded from updates for idempotency).
        },
        "set_like_lists": {"gids"},
        "unique_constraints": {"name", "local_provider_id"},  # Users are uniquely identified by (name, local_provider_id)
        "lookup_field": "name",
    },
    "clusters": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "state",
            "upgrade_state",
            "physical_capacity",
            "logical_capacity",
            "usable_capacity",
            "usable_physical_capacity",
            "usable_logical_capacity",
            "available_physical_capacity",
            "available_logical_capacity",
            "ssd_capacity",
            "usable_ssd_capacity",
            "physical_space_in_use",
            "logical_space_in_use",
            "read_bw",
            "write_bw",
            "read_iops",
            "write_iops",
            "ssd_raid_state",
            "ssd_raid_rebuild_progress",
            "upgrade_progress",
            "leader_cnode",
            "encryption_status",
            "encryption_transition_state",
            "active_sessions_count",
            "current_gen_enabled",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "viewpolicies": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "cluster",
            "tenant_name",
            "views_count",
        },
        "immutable_fields": {"tenant_id"},
        "set_like_lists": {"protocols_audit", "trash_access"},
        "lookup_field": "name",
    },
    "tenants": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "physical_capacity",
            "logical_capacity",
            "views_count",
            "quotas_count",
            "encryption_status",
            "encryption_transition_state",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "quotas": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "state",
            "system_id",  # Internal filesystem system ID, auto-generated by API
            "sync_state",  # Synchronization state (CREATED, SYNCHRONIZED, etc.)
            "cluster",  # Cluster name
            "cluster_id",  # Cluster ID
            "tenant_name",  # Tenant name (computed from tenant_id)
            "internal",  # Whether this is an internal quota
            "used_capacity",
            "used_inodes",
            "used_capacity_tb",
            "used_effective_capacity",
            "used_effective_capacity_tb",
            "used_limited_capacity",  # Used capacity for limited quotas
            "effective_quota_capacity_tb",
            "pretty_state",  # Human-readable state
            "pretty_grace_period",  # Human-readable grace period
            "pretty_grace_period_expiration",  # Human-readable expiration
            "time_to_block",  # Time until blocking (computed)
            "num_exceeded_users",  # Number of users exceeding quota (computed)
            "num_blocked_users",  # Number of blocked users (computed)
            "last_user_quotas_update",  # Last update timestamp (computed)
            "percent_inodes",  # Percentage of inodes used (computed)
            "percent_capacity",  # Percentage of capacity used (computed)
        },
        "immutable_fields": {"path"},
        "set_like_lists": set(),
        "lookup_field": "path",
        "field_normalizers": {
            "user_quotas": normalize_list_by_user_schema,
            "group_quotas": normalize_list_by_user_schema,
            "default_user_quota": normalize_dict_by_user_schema,
            "default_group_quota": normalize_dict_by_user_schema,
        },
    },
    "vippools": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "active_connections",
            "state",
        },
        "immutable_fields": {"role"},
        "set_like_lists": {"cnode_ids", "vlan_ids"},
        "lookup_field": "name",
    },
    "protectionpolicies": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "protected_paths_count",
            "streams_count",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "protectedpaths": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "remote_target_path",
            "last_run_state",
        },
        "immutable_fields": {"source_dir"},
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "snapshots": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "state",
            "data_create_time",
            "logical_capacity",
            "physical_capacity",
        },
        "immutable_fields": {"path"},
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "s3policies": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "users",
            "groups",
            "is_replicated",
            "tenant_name",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "activedirectory": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "state",  # System-managed: UNKNOWN, MEMBER, NOT_A_MEMBER
            "enabled",  # System-managed activation state
            "ldap_id",  # Internal LDAP configuration reference
            "ldap_urls",  # Generated from LDAP config
            "title",  # Auto-generated from domain_name
            "name",  # Auto-generated field
            "tenant_id",  # System-assigned
            "last_ma_pwd_renewal_status",  # System-managed password status
            "scheduled_ma_pwd_change_enabled",  # System-managed schedule flag
            "ma_pwd_change_frequency",  # System default, can vary
            "ma_pwd_update_time",  # System default time
            "preferred_dc_list",  # Resolved from domain, not user input
        },
        "immutable_fields": {
            # LDAP-delegated fields (needed for create, stored in linked LDAP config, can't update)
            "binddn",
            "bindpw",
            "method",
            "port",
            "use_tls",
            "use_ldaps",
            "use_auto_discovery",
            "searchbase",
            "group_searchbase",
            "urls",
        },
        "set_like_lists": set(),
        "ephemeral_fields": {
            "admin_passwd",  # Credentials never returned by API
            "bindpw",  # LDAP bind password never returned (also in immutable)
        },
        "lookup_field": "machine_account_name",
    },
    "ldaps": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "state",
        },
        "immutable_fields": set(),
        "set_like_lists": {"urls"},
        "ephemeral_fields": {
            "bindpw",  # LDAP bind password never returned by API
        },
        "lookup_field": "name",
    },
    "dns": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
        },
        "immutable_fields": set(),
        "set_like_lists": {"domain_suffixes", "vip_pools"},
        "lookup_field": "name",
    },
    "qospolicies": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "groups": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "provider_name",
        },
        "immutable_fields": {
            "local_provider_id",
        },  # local_provider_id is write-once at creation
        "set_like_lists": set(),
        "unique_constraints": {"gid", "local_provider_id"},  # Groups are uniquely identified by (gid, local_provider_id)
        "lookup_field": "name",
    },
    "cnodes": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "state",
            "host_label",
            "ip",
            "ip1",
            "ip2",
            "mgmt_ip",
            "ssd_count",
            "enabled_ssd_count",
            "os_version",
            "bmc_fw_version",
            "psnt",
            "cbox",
            "platform_type",
            "platform_generation",
            "is_mgmt",
            "is_leader",
            "is_vms",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
    "roles": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "created",
            "is_system",
        },
        "immutable_fields": set(),
        "set_like_lists": {"permissions"},
        "lookup_field": "name",
    },
    "certificates": {
        "read_only_fields": {
            "id",
            "guid",
            "url",
            "expiry",
            "fingerprint",
            "cn",
            "issuer",
            "valid_from",
            "valid_to",
        },
        "immutable_fields": set(),
        "set_like_lists": set(),
        "lookup_field": "name",
    },
}


def get_overrides(resource: str) -> Dict[str, Any]:
    """Get overrides for a specific resource.

    Returns default overrides with common read-only fields if resource is not defined.
    """
    # Common read-only fields that appear in most VAST resources
    default_read_only = {
        "id",
        "guid",
        "url",
        "created",
        "state",
    }

    return OVERRIDES.get(
        resource,
        {
            "read_only_fields": default_read_only,
            "immutable_fields": set(),
            "set_like_lists": set(),
            "unique_constraints": set(),
            "lookup_field": "name",
        },
    )


def get_read_only_fields(resource: str) -> Set[str]:
    """Get read-only fields for a resource."""
    return get_overrides(resource).get("read_only_fields", set())


def get_immutable_fields(resource: str) -> Set[str]:
    """Get immutable fields for a resource."""
    return get_overrides(resource).get("immutable_fields", set())


def get_set_like_lists(resource: str) -> Set[str]:
    """Get set-like list fields for a resource."""
    return get_overrides(resource).get("set_like_lists", set())


def get_ephemeral_fields(resource: str) -> Set[str]:
    """Get ephemeral fields for a resource (credentials/secrets never returned by API)."""
    return get_overrides(resource).get("ephemeral_fields", set())


def get_lookup_field(resource: str) -> str:
    """Get lookup field for a resource."""
    return get_overrides(resource).get("lookup_field", "name")


def is_read_only(resource: str, field: str) -> bool:
    """Check if a field is read-only for a resource."""
    return field in get_read_only_fields(resource)


def is_immutable(resource: str, field: str) -> bool:
    """Check if a field is immutable for a resource."""
    return field in get_immutable_fields(resource)


def is_set_like(resource: str, field: str) -> bool:
    """Check if a field is a set-like list for a resource."""
    return field in get_set_like_lists(resource)


def is_ephemeral(resource: str, field: str) -> bool:
    """Check if a field is ephemeral (credentials/secrets) for a resource."""
    return field in get_ephemeral_fields(resource)


def get_unique_constraints(resource: str) -> Set[str]:
    """Get unique constraint fields for a resource."""
    return get_overrides(resource).get("unique_constraints", set())


def is_unique_constraint(resource: str, field: str) -> bool:
    """Check if a field is part of unique constraints."""
    return field in get_unique_constraints(resource)
