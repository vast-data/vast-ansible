#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, VAST Data
# Apache License 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)
# SPDX-License-Identifier: Apache-2.0
"""Framework-level tests for BaseResource / BaseInfoResource.

These exercise the shared CRUD lifecycle once against a mocked VMS REST API
(via requests-mock). Because every generated module delegates to these base
classes, this protects the create/update/delete/idempotency/404/version-gating
behavior for all ~329 modules in one place.
"""

import json
import sys
from pathlib import Path

import pytest

requests_mock = pytest.importorskip("requests_mock")

collection_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(collection_root))

from plugins.module_utils.vast.info_resource import BaseInfoResource
from plugins.module_utils.vast.resource import BaseResource
from plugins.module_utils.vast.sub_endpoint_resource import CrudCapability, SubEndpointResource

BASE = "https://vms.test/api/latest"
# The client only parses bodies advertised as JSON, so every mock must say so.
JSON_CT = {"Content-Type": "application/json"}


class _Exit(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


class _Fail(Exception):
    def __init__(self, kwargs):
        self.kwargs = kwargs


class FakeModule:
    """Minimal AnsibleModule stand-in. exit_json/fail_json raise to unwind."""

    def __init__(self, params, check_mode=False):
        self.params = params
        self.check_mode = check_mode
        self.warnings = []

    def warn(self, msg):
        self.warnings.append(msg)

    def exit_json(self, **kwargs):
        raise _Exit(kwargs)

    def fail_json(self, **kwargs):
        raise _Fail(kwargs)


class WidgetResource(BaseResource):
    resource_name = "widgets"
    singular = "widget"
    lookup_field = "name"


class WidgetInfoResource(BaseInfoResource):
    resource_name = "widgets"
    return_key = "widgets"


def _params(state="present", check=False, **fields):
    params = {
        "vms": {"host": "vms.test", "token": "secret"},
        "state": state,
        "id": None,
        "clear_fields": None,
        "name": fields.pop("name", "w1"),
    }
    params.update(fields)
    return params


def _mock_version(m, version="5.5.0"):
    m.get(f"{BASE}/clusters/", json=[{"id": 1, "sw_version": version}], headers=JSON_CT)


def _run(resource_cls, params, check_mode=False):
    module = FakeModule(params, check_mode=check_mode)
    try:
        resource = resource_cls(module)
        resource.run()
    except _Exit as e:
        return module, ("exit", e.kwargs)
    except _Fail as e:
        return module, ("fail", e.kwargs)
    raise AssertionError("run() did not call exit_json/fail_json")


def test_create_when_absent():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[], headers=JSON_CT)  # lookup -> not found
        posted = {}

        def _post(request, context):
            posted.update(json.loads(request.body))
            return {"id": 7, "name": "w1", "size": 10}

        m.post(f"{BASE}/widgets/", json=_post, headers=JSON_CT)

        _module, (kind, result) = _run(WidgetResource, _params(size=10))

    assert kind == "exit"
    assert result["changed"] is True
    assert result["widgets"]["id"] == 7
    assert posted["size"] == 10


def test_idempotent_no_change():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[{"id": 7, "name": "w1", "size": 10}], headers=JSON_CT)

        _module, (kind, result) = _run(WidgetResource, _params(size=10))

    assert kind == "exit"
    assert result["changed"] is False


def test_update_when_diff():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[{"id": 7, "name": "w1", "size": 10}], headers=JSON_CT)
        patched = {}

        def _patch(request, context):
            patched.update(json.loads(request.body))
            return {"id": 7, "name": "w1", "size": 20}

        m.patch(f"{BASE}/widgets/7/", json=_patch, headers=JSON_CT)

        _module, (kind, result) = _run(WidgetResource, _params(size=20))

    assert kind == "exit"
    assert result["changed"] is True
    assert patched["size"] == 20


def test_delete_when_present():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[{"id": 7, "name": "w1"}], headers=JSON_CT)
        m.delete(f"{BASE}/widgets/7/", status_code=200, json={}, headers=JSON_CT)

        _module, (kind, result) = _run(WidgetResource, _params(state="absent"))

    assert kind == "exit"
    assert result["changed"] is True


def test_absent_noop_when_missing():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[], headers=JSON_CT)

        _module, (kind, result) = _run(WidgetResource, _params(state="absent"))

    assert kind == "exit"
    assert result["changed"] is False


def test_create_in_check_mode_does_not_post():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[], headers=JSON_CT)
        # No POST registered: if create() were called it would raise.

        _module, (kind, result) = _run(WidgetResource, _params(size=10), check_mode=True)

    assert kind == "exit"
    assert result["changed"] is True


def test_404_on_id_lookup_treated_as_absent():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/9/", status_code=404, text="not found")

        params = _params(state="absent")
        params["id"] = 9
        _module, (kind, result) = _run(WidgetResource, params)

    assert kind == "exit"
    assert result["changed"] is False


def test_unsupported_version_fails():
    with requests_mock.Mocker() as m:
        _mock_version(m, version="6.0.0")

        _module, (kind, result) = _run(WidgetResource, _params(size=10))

    assert kind == "fail"
    assert "not supported" in result["msg"].lower()


class BgpConfigResource(SubEndpointResource):
    parent_resource = "cnodes"
    sub_path = "bgp_config"
    path_has_id = True
    parent_id_param = "cnode_id"
    supported_operations = frozenset({CrudCapability.READ, CrudCapability.UPDATE})


def _sub_params(**fields):
    params = {
        "vms": {"host": "vms.test", "token": "secret"},
        "state": "present",
        "wait": True,
        "wait_timeout": 300,
        "cnode_id": 5,
    }
    params.update(fields)
    return params


def test_sub_endpoint_idempotent_no_change():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/cnodes/5/bgp_config/", json=[{"enabled": True}], headers=JSON_CT)

        _module, (kind, result) = _run(BgpConfigResource, _sub_params(enabled=True))

    assert kind == "exit"
    assert result["changed"] is False


def test_sub_endpoint_update_when_diff():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/cnodes/5/bgp_config/", json=[{"enabled": False}], headers=JSON_CT)
        m.patch(f"{BASE}/cnodes/5/bgp_config/", json={"enabled": True}, headers=JSON_CT)

        _module, (kind, result) = _run(BgpConfigResource, _sub_params(enabled=True))

    assert kind == "exit"
    assert result["changed"] is True


def test_info_resource_lists_without_change():
    with requests_mock.Mocker() as m:
        _mock_version(m)
        m.get(f"{BASE}/widgets/", json=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], headers=JSON_CT)

        params = {"vms": {"host": "vms.test", "token": "secret"}}
        _module, (kind, result) = _run(WidgetInfoResource, params)

    assert kind == "exit"
    assert result["changed"] is False
    assert len(result["widgets"]) == 2
