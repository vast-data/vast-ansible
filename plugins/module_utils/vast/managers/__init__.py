"""Resource Manager classes for VAST API operations.

This package contains manager classes that encapsulate business logic for
interacting with VAST API resources. Managers handle:
- CRUD operations (create, read, update, delete)
- Special operations (actions, queries)
- Async task waiting
- Diff computation

Modules delegate to managers for cleaner separation of concerns.
"""

from .base import ResourceManager

__all__ = ["ResourceManager"]
