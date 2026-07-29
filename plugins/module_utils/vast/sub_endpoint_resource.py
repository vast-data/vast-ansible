"""Base class for sub-endpoint Ansible modules.

Provides common runtime logic for all sub-endpoint modules, eliminating
per-module boilerplate. Sub-endpoint modules become thin class declarations:

    class ManagerPassword(SubEndpointResource):
        parent_resource = "managers"
        sub_path = "password"
        path_has_id = False
        supported_operations = frozenset({CrudCapability.UPDATE})
"""

from enum import Enum
from typing import Any, Dict, FrozenSet, List, Set

from ansible.module_utils.basic import AnsibleModule

from .client import VastClient
from .diff import has_changes
from .errors import VastAPIError, VastError
from .schema_overrides import get_overrides
from .version import VersionAwareMixin


class CrudCapability(str, Enum):
    """Supported CRUD operations for a resource or sub-endpoint."""

    CREATE = "create"  # POST
    READ = "read"  # GET
    UPDATE = "update"  # PATCH / PUT
    DELETE = "delete"  # DELETE


class SubEndpointResource(VersionAwareMixin):
    """Base class for sub-endpoint Ansible modules.

    Subclasses must define:
    - parent_resource: str       # e.g. "managers"
    - sub_path: str              # e.g. "password"
    - path_has_id: bool          # True if /parent/{id}/sub_path
    - supported_operations: FrozenSet[CrudCapability]

    Subclasses may override:
    - parent_id_param: str       # default: singular(parent_resource) + "_id"
    - is_async: bool             # default: False
    - related_sub_paths: list    # for action dispatch (e.g. encryption_group_control)
    - get(), create(), update(), delete() for custom behavior
    """

    parent_resource: str = NotImplemented
    sub_path: str = NotImplemented
    path_has_id: bool = True
    supported_operations: FrozenSet[CrudCapability] = frozenset()

    parent_id_param: str = ""
    is_async: bool = False
    related_sub_paths: List[str] = []
    identity_params: List[str] = []
    returns_list: bool = False
    upload_param: str = ""

    # Framework params excluded from payloads
    _EXCLUDE_KEYS: Set[str] = {"vms", "state", "wait", "wait_timeout"}

    def __init__(self, module: AnsibleModule):
        self._init_vast_connection(module)

        self.overrides: Dict[str, Any] = get_overrides(self.parent_resource, self.cluster_mm)

        # Build the set of keys to exclude from payloads
        self._exclude = set(self._EXCLUDE_KEYS)
        if self.path_has_id and self.parent_id_param:
            self._exclude.add(self.parent_id_param)
        if self.related_sub_paths:
            self._exclude.add("action")
        if self.upload_param:
            # The upload param is a local file path, not a JSON body field.
            self._exclude.add(self.upload_param)

    def _version_entity(self) -> str:
        return f"'{self.parent_resource}/{self.sub_path}'"

    @property
    def _api_base(self) -> Any:
        """Build API accessor for this sub-endpoint."""
        api = self.client.api[self.parent_resource]
        if self.path_has_id:
            parent_id = self.params[self.parent_id_param]
            return api[parent_id][self.sub_path]
        return api[self.sub_path]

    def _api_for_action(self, action: str) -> Any:
        """Build API accessor for a specific action (for multi-action sub-endpoints)."""
        api = self.client.api[self.parent_resource]
        if self.path_has_id:
            parent_id = self.params[self.parent_id_param]
            return api[parent_id][action]
        return api[action]

    def _build_payload(self) -> Dict[str, Any]:
        """Build payload from module params, excluding framework params."""
        return {key: value for key, value in self.params.items() if key not in self._exclude and value is not None}

    def _build_search_params(self) -> Dict[str, Any]:
        """Build search params for collection-level GET (no parent ID)."""
        return self._build_payload()

    def get(self) -> Any:
        """Read current state of the sub-endpoint.

        Returns the full list for array-typed endpoints (``returns_list=True``,
        empty -> ``[]``); otherwise the first result, or ``{}`` when empty.
        Callers can therefore treat the return value uniformly without
        re-normalizing the empty case.
        """
        try:
            search = {} if self.path_has_id else self._build_search_params()
            if self.returns_list:
                return self._api_base.get(**search) or []
            return self._api_base.first(**search) or {}
        except Exception as e:
            self.module.fail_json(msg=f"Failed to read {self.sub_path}: {str(e)}")

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create via POST."""
        try:
            result = self._api_base.post(**payload)
        except Exception as e:
            raise VastAPIError(f"Failed to create {self.sub_path}: {e}") from e
        if self.is_async:
            self._wait_for_task(result)
        return result or {}

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update via PATCH."""
        try:
            result = self._api_base.patch(**payload)
        except Exception as e:
            raise VastAPIError(f"Failed to update {self.sub_path}: {e}") from e
        if self.is_async:
            self._wait_for_task(result)
        return result or {}

    def delete(self) -> Dict[str, Any]:
        """Delete the sub-endpoint resource."""
        try:
            result = self._api_base.delete()
        except Exception as e:
            raise VastAPIError(f"Failed to delete {self.sub_path}: {e}") from e
        if self.is_async:
            self._wait_for_task(result)
        return result or {}

    def trigger_action(self, action: str) -> Dict[str, Any]:
        """Trigger a named action (for multi-action sub-endpoints like encryption_group_control)."""
        try:
            result = self._api_for_action(action).post()
        except Exception as e:
            raise VastAPIError(f"Failed to {action}: {e}") from e
        if self.is_async:
            self._wait_for_task(result)
        return result or {}

    def run(self) -> None:
        """Main execution logic -- dispatches based on supported_operations."""
        caps = self.supported_operations
        state = self.params.get("state", "present")

        # Multi-action trigger (e.g. encryption_group_control)
        if self.related_sub_paths:
            self._run_action_trigger()
            return

        # Read-only sub-endpoint
        if caps == frozenset({CrudCapability.READ}):
            self._run_read_only()
            return

        # Read + Update (idempotent sub-resource)
        if CrudCapability.READ in caps and CrudCapability.UPDATE in caps:
            self._run_read_update(state)
            return

        # Action sub-endpoint (POST/PATCH/PUT, possibly with DELETE)
        if CrudCapability.DELETE in caps and state == "absent":
            self._perform_delete()
            return

        self._run_action()

    def _run_read_only(self) -> None:
        """Read-only query module."""
        self.module.exit_json(changed=False, **{self.module_result_key: self.get()})

    def _run_read_update(self, state: str) -> None:
        """Read + update sub-resource (idempotent)."""
        current = self.get()

        if state == "absent":
            if CrudCapability.DELETE in self.supported_operations and current:
                self._perform_delete()
            self.module.exit_json(changed=False, **{self.module_result_key: current or {}})

        payload = self._build_payload()
        if not payload:
            self.module.exit_json(changed=False, **{self.module_result_key: current or {}})

        desired = {k: v for k, v in payload.items() if k not in self.identity_params}
        if current:
            changed = has_changes(current, desired, self.overrides)
        else:
            changed = True

        result = current or {}
        diff_before = dict(current) if current else {}
        diff_after = {}

        if changed and not self.check_mode:
            try:
                result = self.update(payload)
            except VastAPIError as e:
                self.module.fail_json(msg=str(e))
            diff_after = dict(result)
        elif changed:
            diff_after = {**diff_before, **payload}
            result = diff_after

        output: Dict[str, Any] = {"changed": changed, self.module_result_key: result}
        if changed:
            output["diff"] = {"before": diff_before, "after": diff_after}
        self.module.exit_json(**output)

    def _entity_ref(self) -> str:
        """Human-readable identifier used in error messages ('kerberos/42/keytab')."""
        if self.path_has_id and self.parent_id_param:
            parent_id = self.params.get(self.parent_id_param)
            if parent_id is not None:
                return f"{self.parent_resource}/{parent_id}/{self.sub_path}"
        return self.sub_path

    def upload(self, file_path: str) -> Dict[str, Any]:
        """Upload a file via multipart PUT (Swagger ``in: formData`` uploads).

        Wraps any failure (file I/O or transport/API) with the entity path
        + local file, mirroring ``create()``/``update()``/``delete()``.
        """
        entity = self._entity_ref()
        try:
            result = self._api_base.put_file(self.upload_param, file_path)
        except Exception as e:
            raise VastAPIError(f"Failed to upload {entity} from {file_path!r}: {e}") from e
        if self.is_async:
            self._wait_for_task(result)
        return result or {}

    def _run_action(self) -> None:
        """Action sub-endpoint (POST/PATCH/PUT with body)."""
        is_upload = bool(self.upload_param and self.params.get(self.upload_param))

        if self.check_mode:
            if is_upload:
                result: Any = {self.upload_param: self.params[self.upload_param]}
            else:
                result = self._build_payload()
            self.module.exit_json(changed=True, result=result)

        try:
            if is_upload:
                result = self.upload(self.params[self.upload_param])
            else:
                payload = self._build_payload()
                if CrudCapability.CREATE in self.supported_operations:
                    result = self.create(payload)
                elif CrudCapability.UPDATE in self.supported_operations:
                    result = self.update(payload)
                else:
                    result = self.create(payload)
        except VastAPIError as e:
            self.module.fail_json(msg=str(e))

        self.module.exit_json(changed=True, result=result)

    def _perform_delete(self) -> None:
        """Delete action."""
        if not self.check_mode:
            try:
                self.delete()
            except VastAPIError as e:
                self.module.fail_json(msg=str(e))
        self.module.exit_json(changed=True, **{self.module_result_key: {}})

    def _run_action_trigger(self) -> None:
        """Multi-action trigger (e.g. encryption_group_control)."""
        action = self.params.get("action", self.sub_path)

        if self.check_mode:
            self.module.exit_json(changed=True, result={})

        try:
            result = self.trigger_action(action)
        except VastAPIError as e:
            self.module.fail_json(msg=str(e))

        self.module.exit_json(changed=True, result=result)

    @property
    def module_result_key(self) -> str:
        """Key name for the result in module output.

        Defaults to the module name (derived from class name).
        Subclasses can override for custom result keys.
        """
        # Convert CamelCase to snake_case
        name = type(self).__name__
        import re

        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def _wait_for_task(self, response: Any) -> None:
        """Wait for an async task to complete."""
        if not self.params.get("wait", True):
            return
        if response is None:
            return

        task_id = VastClient.extract_task_id(response)
        if task_id:
            try:
                self.client.wait_for_task(task_id, timeout=self.params.get("wait_timeout", 300))
            except VastError as e:
                self.module.fail_json(msg=f"Async task {task_id} failed: {str(e)}")
