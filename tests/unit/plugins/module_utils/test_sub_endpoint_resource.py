#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Unit tests for SubEndpointResource read behavior (array vs single object)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add collection root to path for importing module_utils
collection_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(collection_root))

from plugins.module_utils.vast.sub_endpoint_resource import (  # noqa: E402
    CrudCapability,
    SubEndpointResource,
)


class _FakeApiBase:
    """Stand-in for the client API segment, mirroring get()/first() semantics."""

    def __init__(self, results):
        self._results = list(results)
        self.get_calls = []
        self.first_calls = []

    def get(self, **params):
        self.get_calls.append(params)
        return list(self._results)

    def first(self, **params):
        self.first_calls.append(params)
        return self._results[0] if self._results else None


def _make_sub(
    returns_list,
    results,
    path_has_id=True,
    supported=frozenset({CrudCapability.READ}),
    parent_resource="vms",
    overrides=None,
):
    """Build a SubEndpointResource instance bypassing __init__ (no live VMS)."""
    fake = _FakeApiBase(results)

    class _S(SubEndpointResource):
        pass

    _S.parent_resource = parent_resource
    _S.sub_path = "configured_idps"
    _S.path_has_id = path_has_id
    _S.returns_list = returns_list
    _S.supported_operations = supported
    _S._api_base = property(lambda self: fake)  # type: ignore[assignment]

    sub = _S.__new__(_S)
    sub.module = MagicMock()
    sub.params = {}
    sub.check_mode = False
    sub._exclude = set(SubEndpointResource._EXCLUDE_KEYS)
    sub.overrides = overrides or {}
    sub._fake = fake
    return sub


class TestGetReturnsList:
    """returns_list=True surfaces the whole array response."""

    def test_multiple_items_survive(self):
        """All elements survive instead of collapsing to the first."""
        sub = _make_sub(returns_list=True, results=["okta", "azure", "ping"])
        assert sub.get() == ["okta", "azure", "ping"]

    def test_empty_stays_empty_list(self):
        """An empty collection reads back as []."""
        sub = _make_sub(returns_list=True, results=[])
        assert sub.get() == []

    def test_routes_through_get_not_first(self):
        """The array path uses get(), never first()."""
        sub = _make_sub(returns_list=True, results=["okta"])
        sub.get()
        assert sub._fake.get_calls == [{}]
        assert sub._fake.first_calls == []


class TestGetSingleObject:
    """returns_list=False keeps the legacy single-object behavior."""

    def test_collapses_to_first(self):
        """Non-list endpoints still return only the first element."""
        sub = _make_sub(returns_list=False, results=["okta", "azure"])
        assert sub.get() == "okta"

    def test_empty_returns_empty_dict(self):
        """An empty result is normalized to ``{}`` inside ``get()`` itself."""
        sub = _make_sub(returns_list=False, results=[])
        assert sub.get() == {}

    def test_collection_level_passes_search_params(self):
        """Without a parent id, search params are forwarded to the API call."""
        sub = _make_sub(returns_list=False, results=[{"a": 1}], path_has_id=False)
        sub.params = {"name": "foo", "vms": {}, "state": "present"}
        sub.get()
        assert sub._fake.first_calls == [{"name": "foo"}]


class TestRunReadOnly:
    """_run_read_only emits a shape-correct result for both flavors."""

    def test_list_result_emitted_intact(self):
        sub = _make_sub(returns_list=True, results=["okta", "azure", "ping"])
        sub._run_read_only()
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs["changed"] is False
        assert kwargs[sub.module_result_key] == ["okta", "azure", "ping"]

    def test_empty_list_emitted_as_list(self):
        sub = _make_sub(returns_list=True, results=[])
        sub._run_read_only()
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs[sub.module_result_key] == []

    def test_empty_single_emitted_as_dict(self):
        sub = _make_sub(returns_list=False, results=[])
        sub._run_read_only()
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs[sub.module_result_key] == {}


class TestRunReadUpdateSetLikeIdempotency:
    """Order-insensitive list fields."""

    def _sub_with_current(self, current, supported_ops, set_like_lists):
        sub = _make_sub(
            returns_list=False,
            results=[current],
            path_has_id=False,
            supported=supported_ops,
            parent_resource="groups",
            overrides={"set_like_lists": set_like_lists},
        )
        # Real Ansible's exit_json raises SystemExit; mimic that so control
        # flow stops on the first exit_json call, matching production.
        sub.module.exit_json.side_effect = SystemExit
        return sub

    def test_s3_policies_ids_order_difference_is_not_a_change(self):
        """API returns [14, 15]; user sends [15, 14] — must be idempotent."""
        sub = self._sub_with_current(
            current={"gid": 1, "tenant_id": 53, "s3_policies_ids": [14, 15]},
            supported_ops=frozenset({CrudCapability.READ, CrudCapability.UPDATE}),
            set_like_lists={"s3_policies_ids"},
        )
        sub.params = {
            "gid": 1,
            "tenant_id": 53,
            "s3_policies_ids": [15, 14],
            "state": "present",
        }
        try:
            sub._run_read_update("present")
        except SystemExit:
            pass
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs["changed"] is False, "Set-like list reorder must be idempotent"

    def test_order_difference_is_a_change_when_not_set_like(self):
        """Sanity check: without set_like_lists, order still matters."""
        sub = self._sub_with_current(
            current={"gid": 1, "tenant_id": 53, "s3_policies_ids": [14, 15]},
            supported_ops=frozenset({CrudCapability.READ, CrudCapability.UPDATE}),
            set_like_lists=set(),
        )
        sub.params = {
            "gid": 1,
            "tenant_id": 53,
            "s3_policies_ids": [15, 14],
            "state": "present",
        }
        try:
            sub._run_read_update("present")
        except SystemExit:
            pass
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs["changed"] is True

    def test_real_change_still_detected_with_set_like(self):
        """Adding a new id must still register as a change."""
        sub = self._sub_with_current(
            current={"gid": 1, "tenant_id": 53, "s3_policies_ids": [14, 15]},
            supported_ops=frozenset({CrudCapability.READ, CrudCapability.UPDATE}),
            set_like_lists={"s3_policies_ids"},
        )
        sub.params = {
            "gid": 1,
            "tenant_id": 53,
            "s3_policies_ids": [14, 15, 16],
            "state": "present",
        }
        sub.check_mode = True  # avoid needing update() plumbing
        try:
            sub._run_read_update("present")
        except SystemExit:
            pass
        kwargs = sub.module.exit_json.call_args.kwargs
        assert kwargs["changed"] is True
