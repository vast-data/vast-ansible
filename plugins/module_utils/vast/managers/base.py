"""Base Resource Manager class.

Provides common functionality for all resource managers.
"""

from typing import Any, Dict, Optional

from ..client import VastClient
from ..diff import compute_patch, normalize_resource
from ..errors import VastAPIError
from ..schema_overrides import get_overrides
from ..waiter import TaskWaiter


class ResourceManager:
    """Base class for VAST resource managers.

    Managers encapsulate business logic for resource operations,
    separating concerns from Ansible module boilerplate.

    Subclasses must override:
    - resource_name: str (e.g., "views", "users")
    - lookup_field: str (e.g., "path", "name")

    Subclasses may override:
    - async_create: bool = False
    - async_update: bool = False
    - async_delete: bool = False
    """

    resource_name: str = NotImplemented
    lookup_field: str = "name"

    # Async operation flags
    async_create: bool = False
    async_update: bool = False
    async_delete: bool = False

    def __init__(self, client: VastClient, wait: bool = True, wait_timeout: int = 300):
        """Initialize the manager.

        Args:
            client: VastClient instance
            wait: Whether to wait for async operations
            wait_timeout: Timeout in seconds for async operations
        """
        self.client = client
        self.wait = wait
        self.wait_timeout = wait_timeout
        self.overrides = get_overrides(self.resource_name)

    def get(self, lookup_value: str) -> Optional[Dict[str, Any]]:
        """Get resource by lookup field value.

        Args:
            lookup_value: Value of the lookup field

        Returns:
            Resource dict if found, None otherwise

        Raises:
            VastAPIError: On API errors
        """
        try:
            api = getattr(self.client.api, self.resource_name)
            results = api.get(**{self.lookup_field: lookup_value})
        except Exception as e:
            raise VastAPIError(f"Failed to get {self.resource_name} by {self.lookup_field} " f"'{lookup_value}': {e}") from e

        if not results:
            return None
        return results[0] if isinstance(results, list) else results

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
            raise VastAPIError(f"Failed to create {self.resource_name}: {e}") from e

        # Wait for async create if needed
        if self.async_create and self.wait:
            self._wait_for_task(result)

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
            raise VastAPIError(f"Failed to update {self.resource_name} {resource_id}: {e}") from e

        # Wait for async update if needed
        if self.async_update and self.wait:
            self._wait_for_task(result)

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
            raise VastAPIError(f"Failed to delete {self.resource_name} {resource_id}: {e}") from e

        # Wait for async delete if needed
        if self.async_delete and self.wait:
            self._wait_for_task(result)

        return result

    def compute_diff(self, current: Dict[str, Any], desired: Dict[str, Any]) -> Dict[str, Any]:
        """Compute patch between current and desired state.

        Args:
            current: Current resource state
            desired: Desired resource state

        Returns:
            Patch dict with fields to update
        """
        current_normalized = normalize_resource(current, self.overrides)
        desired_normalized = normalize_resource(desired, self.overrides)
        return compute_patch(current_normalized, desired_normalized, self.overrides)

    def _wait_for_task(self, response: Dict[str, Any]) -> None:
        """Wait for an async task to complete.

        Args:
            response: API response that may contain task_id

        Raises:
            VastAPIError: If task fails
        """
        # Extract task ID
        task_id = self._extract_task_id(response)

        # No task ID = synchronous operation
        if not task_id:
            return

        # Wait for task
        waiter = TaskWaiter(self.client, timeout=self.wait_timeout)
        waiter.wait_for_task(task_id)

    def _extract_task_id(self, response: Dict[str, Any]) -> Optional[int]:
        """Extract task ID from response.

        Args:
            response: API response

        Returns:
            Task ID if found, None otherwise
        """
        # Direct task_id field
        if "task_id" in response:
            return response["task_id"]

        # Nested async_task object
        if "async_task" in response:
            async_task = response.get("async_task", {})
            task_id = async_task.get("id") or async_task.get("task_id")
            if task_id:
                return task_id

        # Task object at root
        if "id" in response and response.get("type") == "async_task":
            return response["id"]

        return None
