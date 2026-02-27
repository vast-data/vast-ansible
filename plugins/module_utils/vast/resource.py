"""Base Resource class for Ansible modules.

Provides common CRUD functionality for all resource modules,
eliminating code duplication across 100+ generated modules.
"""

from typing import Any, Dict, Optional

from ansible.module_utils.basic import AnsibleModule

from .auth import build_connection, validate_auth
from .client import VastClient
from .diff import compute_patch, normalize_resource
from .errors import VastAPIError
from .schema_overrides import get_overrides
from .version import ensure_supported_version
from .waiter import TaskWaiter


class BaseResource:
    """Base class for all Ansible module resources.

    Provides common CRUD operations and idempotent lifecycle management.

    Subclasses must define:
    - resource_name: str  # e.g., "alarms", "views"
    - singular: str       # e.g., "alarm", "view"
    - lookup_field: str   # e.g., "name", "path"

    Subclasses may override:
    - async_create: bool = False
    - async_update: bool = False
    - async_delete: bool = False
    - include_ephemeral_in_updates: bool = False  # Set True to allow password updates (breaks idempotency)
    - get(), create(), update(), delete() methods for custom behavior
    """

    resource_name: str = NotImplemented
    singular: str = NotImplemented
    lookup_field: str = "name"

    # Override these for async resources
    async_create: bool = False
    async_update: bool = False
    async_delete: bool = False

    # Override this to include ephemeral fields (passwords/secrets) in update patches
    # This breaks idempotency but allows password updates. Default False for idempotency.
    include_ephemeral_in_updates: bool = False

    def __init__(self, module: AnsibleModule):
        """Initialize the resource manager.

        Args:
            module: AnsibleModule instance
        """
        self.module = module
        self.params = module.params
        self.check_mode = module.check_mode

        # Validate authentication
        try:
            validate_auth(self.params)
        except Exception as e:
            module.fail_json(msg=str(e))

        # Build connection and client
        conn = build_connection(self.params)
        try:
            self.client = VastClient(conn)
        except RuntimeError as e:
            module.fail_json(msg=str(e))

        # Validate product version
        ensure_supported_version(module, self.client, min_version=(5, 4, 0), max_version=(5, 5, 0))

        # Get schema overrides for this resource
        self.overrides = get_overrides(self.resource_name)

    def _get_field_value(self, resource: Dict[str, Any], field_name: str) -> Any:
        """Get field value from resource, handling nested objects.

        The API often returns nested objects (e.g., local_provider: {id: 1, name: "default"}),
        but module parameters use flat IDs (e.g., local_provider_id: 1).
        This function handles both cases.
        """
        # Try direct access first
        value = resource.get(field_name)
        if value is not None:
            return value

        # If field ends with _id, try nested object access
        # e.g., local_provider_id -> local_provider.id
        if field_name.endswith("_id"):
            nested_field = field_name[:-3]  # Remove "_id" suffix
            nested_obj = resource.get(nested_field)
            if isinstance(nested_obj, dict):
                return nested_obj.get("id")
            # Handle case where nested object is already an int
            if isinstance(nested_obj, int):
                return nested_obj

        return None

    def _is_not_found_error(self, exception: Exception) -> bool:
        """Check if exception looks like a 404 Not Found error.

        Args:
            exception: Exception from API call

        Returns:
            True if this looks like a not-found error, False otherwise
        """
        # Check common patterns in exception messages
        err_str = str(exception).lower()
        return any(
            pattern in err_str
            for pattern in [
                "404",
                "not found",
                "does not exist",
                "no such",
                "resource not found",
            ]
        )

    def _as_list(self, result: Any) -> list:
        """Ensure result is a list.

        Args:
            result: API result (can be dict, list, or None)

        Returns:
            List representation of result
        """
        if result is None:
            return []
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
        return []

    def get(
        self,
        lookup_value: Optional[str] = None,
        resource_id: Optional[int] = None,
        unique_constraints: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get resource by lookup field or ID, with optional composite key filtering.

        Args:
            lookup_value: Value of the lookup field (e.g., name="foo")
            resource_id: Optional ID for direct lookup (bypasses lookup field search)
            unique_constraints: Optional dict of fields that together uniquely identify the resource

        Returns:
            Resource dict if found, None otherwise

        Raises:
            VastAPIError: On API errors (except 404/not-found)

        Note: If unique_constraints is provided, multiple matches are filtered to find the exact resource.
        """
        try:
            api = getattr(self.client.api, self.resource_name)

            # If ID provided, use direct ID lookup (most reliable)
            if resource_id is not None:
                try:
                    res = api[resource_id].get()
                    res_list = self._as_list(res)
                    return res_list[0] if res_list else None
                except Exception as e:
                    # Only treat genuine not-found as None; re-raise auth/connection errors
                    if self._is_not_found_error(e):
                        return None
                    raise

            # If unique constraints are provided and lookup_field is not part of them,
            # search by unique constraints directly (enables rename operations)
            if unique_constraints and self.lookup_field not in unique_constraints:
                results = self._as_list(api.get(**unique_constraints))
                if len(results) == 1:
                    return results[0]
                if len(results) > 1:
                    self.module.fail_json(
                        msg=(f"Multiple {self.singular} resources found with " f"unique_constraints={unique_constraints}")
                    )
                # len(results) == 0: no resource matches, fall through to lookup_field search

            # Try lookup field-based lookup
            if lookup_value:
                results = self._as_list(api.get(**{self.lookup_field: lookup_value}))

                # Apply unique constraint filtering if specified
                if unique_constraints and results:
                    matches = [r for r in results if all(self._get_field_value(r, k) == v for k, v in unique_constraints.items())]
                    if len(matches) == 1:
                        return matches[0]
                    if len(matches) > 1:
                        self.module.fail_json(
                            msg=(
                                f"Multiple {self.singular} resources found with "
                                f"{self.lookup_field}='{lookup_value}' and unique_constraints={unique_constraints}"
                            )
                        )
                    # len(matches) == 0: no resource matches the unique constraints
                    return None
                elif results:
                    # No constraints: return first result (backward compatible)
                    return results[0] if results else None

            return None
        except Exception as e:
            raise VastAPIError(
                f"Failed to get {self.singular} (lookup_field={self.lookup_field}, lookup_value={lookup_value}, id={resource_id}): {e}"
            ) from e

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new resource.

        Args:
            payload: Resource data

        Returns:
            Created resource dict

        Raises:
            VastAPIError: On API errors
        """
        try:
            api = getattr(self.client.api, self.resource_name)
            result = api.post(**payload)
        except Exception as e:
            raise VastAPIError(f"Failed to create {self.singular}: {e}") from e

        # Wait for async create if needed
        if self.async_create and self.params.get("wait", True):
            self._wait_for_task(result)
            # Refresh to get actual resource data (not task object)
            if "id" in result and result.get("type") != "async_task":
                refreshed = self.get(resource_id=result["id"])
                if refreshed:
                    return refreshed

        return result

    def update(self, resource_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing resource.

        Args:
            resource_id: Resource ID
            patch: Fields to update

        Returns:
            Updated resource dict

        Raises:
            VastAPIError: On API errors
        """
        try:
            api = getattr(self.client.api, self.resource_name)
            result = api[resource_id].patch(**patch)
        except Exception as e:
            raise VastAPIError(f"Failed to update {self.singular} {resource_id}: {e}") from e

        # Wait for async update if needed
        if self.async_update and self.params.get("wait", True):
            self._wait_for_task(result)
            # Refresh to get actual resource data (not task object)
            refreshed = self.get(resource_id=resource_id)
            if refreshed:
                return refreshed

        return result

    def delete(self, resource_id: int) -> Dict[str, Any]:
        """Delete a resource.

        Args:
            resource_id: Resource ID

        Returns:
            Delete response (may contain task_id for async)

        Raises:
            VastAPIError: On API errors
        """
        try:
            api = getattr(self.client.api, self.resource_name)
            result = api[resource_id].delete()
            result = result if result else {}
        except Exception as e:
            raise VastAPIError(f"Failed to delete {self.singular} {resource_id}: {e}") from e

        # Wait for async delete if needed
        if self.async_delete and self.params.get("wait", True):
            self._wait_for_task(result)

        return result

    def build_desired_state(self) -> Dict[str, Any]:
        """Build desired state from module parameters.

        Excludes connection parameters and framework fields.

        Returns:
            Dict of resource fields from module parameters
        """
        # Exclude framework parameters (connection, state, wait, etc.)
        exclude_keys = {
            "vms",  # Connection parameters are nested in this dict
            "id",  # ID is for lookup only, not part of desired state
            "state",
            "wait",
            "wait_timeout",
            "query",
            # Special operation parameters (actions, not resource fields)
            "set_posix_primary",
            "revoke",
            "revoke_access_keys",
        }

        desired = {}
        for key, value in self.params.items():
            if key not in exclude_keys and value is not None:
                desired[key] = value

        return desired

    def run(self) -> None:
        """Main execution logic - handles full CRUD lifecycle.

        This method:
        1. Gets current resource state
        2. Determines what action to take (create/update/delete/none)
        3. Performs the action with check_mode support
        4. Computes diffs for changed resources
        5. Exits with appropriate result
        """
        # Check for special operation parameters (BaseResource only supports CRUD operations)
        # Modules with special operations should use custom implementations (see ldaps, apitokens, iamroles, etc.)
        special_ops = {
            "set_posix_primary",
            "revoke",
            "revoke_access_keys",
        }
        active_special_ops = [op for op in special_ops if self.params.get(op)]

        if active_special_ops:
            # Special operations requested - report that they would be performed in check mode
            if self.check_mode:
                self.module.exit_json(
                    changed=True,
                    msg=f"Check mode: Would perform special operation(s): {', '.join(active_special_ops)}",
                    **{self.resource_name: {}},
                )
            # In non-check mode, special operations are not supported by BaseResource
            # Modules requiring special operations should use custom implementations (see ldaps, apitokens, etc.)
            self.module.fail_json(
                msg=f"Special operations ({', '.join(active_special_ops)}) require custom module implementation. "
                f"The BaseResource class only supports standard CRUD operations (create, read, update, delete)."
            )

        state = self.params.get("state", "present")
        lookup_value = self.params.get(self.lookup_field)
        resource_id = self.params.get("id")

        # Validate that we have a way to identify the resource for state=present
        if not lookup_value and not resource_id and state == "present":
            self.module.fail_json(msg=f"Either '{self.lookup_field}' or 'id' parameter is required when state=present")

        # Build unique constraints dict from params for composite key lookups
        unique_constraint_fields = self.overrides.get("unique_constraints", set())
        unique_constraints = None
        if unique_constraint_fields:
            unique_constraints = {k: self.params.get(k) for k in unique_constraint_fields if self.params.get(k) is not None}
            # Only include lookup_field in constraints if it's explicitly part of unique_constraint_fields
            # This allows rename operations when lookup_field is not a unique constraint (e.g., groups by gid+local_provider_id)
            if unique_constraints and lookup_value and self.lookup_field in unique_constraint_fields:
                if self.lookup_field not in unique_constraints:
                    unique_constraints[self.lookup_field] = lookup_value

        # Get current state
        try:
            current = (
                self.get(lookup_value, resource_id, unique_constraints=unique_constraints)
                if (lookup_value or resource_id)
                else None
            )
        except VastAPIError as e:
            self.module.fail_json(msg=str(e))

        changed = False
        result_data = {}
        diff_before = {}
        diff_after = {}

        if state == "absent":
            if current:
                if not self.check_mode:
                    try:
                        self.delete(current["id"])
                    except VastAPIError as e:
                        self.module.fail_json(msg=str(e))
                changed = True
                diff_before = dict(current)
                diff_after = {}
            result_data = current or {}

        else:  # state == present
            desired = self.build_desired_state()

            if not current:
                # Create new resource
                if not self.check_mode:
                    try:
                        result_data = self.create(desired)
                    except VastAPIError as e:
                        self.module.fail_json(msg=str(e))
                else:
                    result_data = desired
                changed = True
                diff_before = {}
                diff_after = dict(result_data)
            else:
                # Check if update needed
                current_normalized = normalize_resource(current, self.overrides, exclude_immutable=True)
                # Include ephemeral fields in update patches only if explicitly enabled (breaks idempotency)
                desired_normalized = normalize_resource(
                    desired, self.overrides, exclude_immutable=True, include_ephemeral=self.include_ephemeral_in_updates
                )
                patch = compute_patch(current_normalized, desired_normalized, self.overrides)

                if patch:
                    if not self.check_mode:
                        try:
                            result_data = self.update(current["id"], patch)
                        except VastAPIError as e:
                            self.module.fail_json(msg=str(e))
                    else:
                        result_data = {**current, **patch}
                    changed = True
                    diff_before = dict(current)
                    diff_after = dict(result_data)
                else:
                    result_data = current

        # Build result
        result = {
            "changed": changed,
            self.resource_name: result_data,
        }
        # Include diff when changed (Ansible will only show it if --diff flag is used)
        if changed and (diff_before or diff_after):
            result["diff"] = {"before": diff_before, "after": diff_after}

        self.module.exit_json(**result)

    def _wait_for_task(self, response: Dict[str, Any]) -> None:
        """Wait for an async task to complete.

        Args:
            response: API response that may contain task_id

        Raises:
            VastAPIError: If task fails
        """
        task_id = self._extract_task_id(response)
        if task_id:
            waiter = TaskWaiter(self.client, timeout=self.params.get("wait_timeout", 300))
            try:
                waiter.wait_for_task(task_id)
            except VastAPIError as e:
                self.module.fail_json(msg=f"Async task {task_id} failed: {str(e)}")

    def _extract_task_id(self, response: Dict[str, Any]) -> Optional[int]:
        """Extract task ID from response.

        Args:
            response: API response

        Returns:
            Task ID if found, None otherwise
        """
        if response is None:
            # No result, no task to wait for
            return None
        elif not isinstance(response, dict):
            # Unexpected response type
            self.module.fail_json(msg=f"Unexpected response type: {type(response)}")
            return None

        # Direct task_id field
        if "task_id" in response:
            return response["task_id"]

        # Nested async_task object
        if "async_task" in response:
            async_task = response.get("async_task") or {}
            task_id = async_task.get("id") or async_task.get("task_id")
            if task_id:
                return task_id

        # Task object at root
        if "id" in response and response.get("type") == "async_task":
            return response["id"]

        return None
