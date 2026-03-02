"""Async task waiter for VAST operations.

Provides polling functionality for long-running VAST operations that return
async task markers. Used by modules that need to wait for operations to complete.
"""

import time
from typing import Any, Callable, Dict, Optional

from .errors import VastAPIError


class TaskWaiter:
    """Wait for async VAST tasks to complete.

    VAST operations that modify resources may return async task markers.
    This class polls the task status until completion or timeout.
    """

    # Task states
    STATE_PENDING = "PENDING"
    STATE_RUNNING = "RUNNING"
    STATE_COMPLETED = "COMPLETED"
    STATE_SUCCESS = "SUCCESS"
    STATE_FAILED = "FAILED"
    STATE_ERROR = "ERROR"
    STATE_CANCELLED = "CANCELLED"

    TERMINAL_STATES = {STATE_COMPLETED, STATE_SUCCESS, STATE_FAILED, STATE_ERROR, STATE_CANCELLED}
    SUCCESS_STATES = {STATE_COMPLETED, STATE_SUCCESS}

    def __init__(
        self,
        client: Any,
        timeout: int = 300,
        poll_interval: int = 5,
    ):
        """Initialize the waiter.

        Args:
            client: VastClient instance.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between polls in seconds.
        """
        self.client = client
        self.timeout = timeout
        self.poll_interval = poll_interval

    def wait_for_task(self, task_id: int) -> Dict[str, Any]:
        """Wait for an async task to complete.

        Args:
            task_id: The ID of the task to wait for.

        Returns:
            The final task state dictionary.

        Raises:
            VastAPIError: If the task fails or times out.
        """
        start_time = time.time()
        last_state = None

        while True:
            elapsed = time.time() - start_time

            if elapsed >= self.timeout:
                raise VastAPIError(f"Task {task_id} timed out after {self.timeout} seconds. " f"Last known state: {last_state}")

            task = self._get_task(task_id)
            state = task.get("state", task.get("status", "UNKNOWN"))
            last_state = state

            if state in self.SUCCESS_STATES:
                return task

            if state in self.TERMINAL_STATES:
                error = task.get("error", task.get("message", "Unknown error"))
                raise VastAPIError(f"Task {task_id} failed with state '{state}': {error}")

            # Still running, wait and poll again
            time.sleep(self.poll_interval)

    def _get_task(self, task_id: int) -> Dict[str, Any]:
        """Get task status from API.

        Args:
            task_id: The task ID.

        Returns:
            Task status dictionary.
        """
        try:
            # Try vtasks endpoint (common for VAST)
            tasks = self.client.api.vtasks.get(id=task_id)
            if tasks:
                return tasks[0] if isinstance(tasks, list) else tasks

            # Fallback to async_tasks if vtasks doesn't exist
            tasks = self.client.api.async_tasks.get(id=task_id)
            if tasks:
                return tasks[0] if isinstance(tasks, list) else tasks

            raise VastAPIError(f"Task {task_id} not found")
        except AttributeError:
            # API endpoint doesn't exist
            raise VastAPIError(f"Cannot retrieve task {task_id}: " "Neither vtasks nor async_tasks endpoint available") from None
        except Exception as e:
            raise VastAPIError(f"Failed to get task {task_id}: {e}") from e

    def wait_for_condition(
        self,
        check_fn: Callable[[], bool],
        description: str = "condition",
    ) -> None:
        """Wait for a custom condition to become true.

        Args:
            check_fn: Function that returns True when condition is met.
            description: Description of what we're waiting for (for errors).

        Raises:
            VastAPIError: If condition is not met within timeout.
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed >= self.timeout:
                raise VastAPIError(f"Timed out waiting for {description} after {self.timeout} seconds")

            try:
                if check_fn():
                    return
            except Exception:
                # Log but continue polling
                pass

            time.sleep(self.poll_interval)


def extract_task_id(response: Dict[str, Any]) -> Optional[int]:
    """Extract task ID from an async response.

    VAST async responses may contain task info in various formats.

    Args:
        response: API response dictionary.

    Returns:
        Task ID if found, None otherwise.
    """
    # Direct task_id field
    if "task_id" in response:
        return response["task_id"]

    # Nested async_task object
    async_task = response.get("async_task", {})
    if "id" in async_task:
        return async_task["id"]
    if "task_id" in async_task:
        return async_task["task_id"]

    # Task object at root
    if "id" in response and response.get("type") == "async_task":
        return response["id"]

    return None


def wait_for_resource_state(
    client: Any,
    resource_type: str,
    resource_id: int,
    target_state: str,
    timeout: int = 300,
    poll_interval: int = 5,
) -> Dict[str, Any]:
    """Wait for a resource to reach a specific state.

    Args:
        client: VastClient instance.
        resource_type: Type of resource (e.g., 'views', 'clusters').
        resource_id: ID of the resource.
        target_state: Desired state value.
        timeout: Maximum time to wait.
        poll_interval: Time between polls.

    Returns:
        The resource when it reaches the target state.

    Raises:
        VastAPIError: If resource doesn't reach state within timeout.
    """
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time

        if elapsed >= timeout:
            raise VastAPIError(
                f"Resource {resource_type}/{resource_id} did not reach " f"state '{target_state}' within {timeout} seconds"
            )

        try:
            api = getattr(client.api, resource_type)
            resource = api[resource_id].get()

            if isinstance(resource, list):
                resource = resource[0] if resource else {}

            state = resource.get("state", resource.get("status"))

            if state == target_state:
                return resource

            # Check for error states
            if state in ("ERROR", "FAILED", "DELETED"):
                error = resource.get("error", resource.get("message", "Unknown error"))
                raise VastAPIError(f"Resource {resource_type}/{resource_id} entered " f"error state '{state}': {error}")
        except VastAPIError:
            raise
        except Exception:
            # Transient error, continue polling
            pass

        time.sleep(poll_interval)
