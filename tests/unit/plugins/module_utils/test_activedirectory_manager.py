"""Unit tests for ActivedirectoryManager class.

Tests the business logic in the manager independently of Ansible.
"""

from unittest.mock import MagicMock

import pytest
from ansible_collections.vastdata.vms.plugins.module_utils.vast.errors import VastAPIError
from ansible_collections.vastdata.vms.plugins.module_utils.vast.managers.activedirectory import ActivedirectoryManager


class TestActivedirectoryManager:
    """Test cases for ActivedirectoryManager."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock VastClient."""
        client = MagicMock()
        client.api.activedirectory = MagicMock()
        return client

    @pytest.fixture
    def manager(self, mock_client):
        """Create an ActivedirectoryManager instance."""
        return ActivedirectoryManager(mock_client, wait=False)

    def test_manager_initialization(self, manager):
        """Test manager is properly initialized."""
        assert manager.resource_name == "activedirectory"
        assert manager.lookup_field == "machine_account_name"
        assert manager.wait is False

    def test_manager_async_flags(self, manager):
        """Test async operation flags are set correctly."""
        assert manager.async_create is False
        assert manager.async_update is True  # AD has async update
        assert manager.async_delete is False

    def test_get_ad_success(self, manager, mock_client):
        """Test getting an AD configuration."""
        # Mock API response
        mock_client.api.activedirectory.get.return_value = [
            {"id": 1, "machine_account_name": "vast-server", "domain_name": "example.com"}
        ]

        result = manager.get("vast-server")

        assert result is not None
        assert result["machine_account_name"] == "vast-server"
        mock_client.api.activedirectory.get.assert_called_once_with(machine_account_name="vast-server")

    def test_get_ad_not_found(self, manager, mock_client):
        """Test getting non-existent AD returns None."""
        mock_client.api.activedirectory.get.return_value = []

        result = manager.get("nonexistent")

        assert result is None

    def test_create_ad(self, manager, mock_client):
        """Test joining Active Directory."""
        payload = {
            "machine_account_name": "vast-server",
            "domain_name": "example.com",
            "binddn": "CN=Administrator,CN=Users,DC=example,DC=com",
            "bindpw": "password",
        }
        mock_client.api.activedirectory.post.return_value = {"id": 1, **payload}

        result = manager.create(payload)

        assert result["id"] == 1
        assert result["machine_account_name"] == "vast-server"
        mock_client.api.activedirectory.post.assert_called_once_with(**payload)

    def test_update_ad(self, manager, mock_client):
        """Test updating AD configuration."""
        patch_data = {"use_tls": True}
        mock_client.api.activedirectory.__getitem__.return_value.patch.return_value = {
            "id": 1,
            "machine_account_name": "vast-server",
            "use_tls": True,
        }

        result = manager.update(1, patch_data)

        assert result["use_tls"] is True
        mock_client.api.activedirectory.__getitem__.assert_called_once_with(1)

    def test_delete_ad(self, manager, mock_client):
        """Test leaving Active Directory."""
        mock_client.api.activedirectory.__getitem__.return_value.delete.return_value = {}

        result = manager.delete(1)

        assert result == {}
        mock_client.api.activedirectory.__getitem__.assert_called_once_with(1)

    # ====================
    # Special Operations Tests
    # ====================

    def test_refresh_operation(self, manager, mock_client):
        """Test refresh special operation."""
        mock_client.api.activedirectory.__getitem__.return_value.refresh.patch.return_value = {"status": "success"}

        result = manager.refresh(1)

        assert result["changed"] is True  # PATCH operations change state
        assert result["result"]["status"] == "success"
        mock_client.api.activedirectory.__getitem__.assert_called_once_with(1)
        mock_client.api.activedirectory.__getitem__.return_value.refresh.patch.assert_called_once()

    def test_domains_query(self, manager, mock_client):
        """Test domains query operation."""
        mock_client.api.activedirectory.__getitem__.return_value.domains.get.return_value = {"domains": ["example.com", "test.com"]}

        result = manager.domains(1)

        assert result["changed"] is False  # GET operations don't change state
        assert "domains" in result["result"]
        mock_client.api.activedirectory.__getitem__.assert_called_once_with(1)

    def test_dcs_query(self, manager, mock_client):
        """Test DCs query operation."""
        mock_client.api.activedirectory.__getitem__.return_value.dcs.get.return_value = {
            "dcs": ["dc1.example.com", "dc2.example.com"]
        }

        result = manager.dcs(1)

        assert result["changed"] is False
        assert "dcs" in result["result"]

    def test_gcs_query(self, manager, mock_client):
        """Test GCs query operation."""
        mock_client.api.activedirectory.__getitem__.return_value.gcs.get.return_value = {"gcs": ["gc1.example.com"]}

        result = manager.gcs(1)

        assert result["changed"] is False
        assert "gcs" in result["result"]

    def test_current_gc_query(self, manager, mock_client):
        """Test current_gc query operation."""
        mock_client.api.activedirectory.__getitem__.return_value.current_gc.get.return_value = {"current_gc": "gc1.example.com"}

        result = manager.current_gc(1)

        assert result["changed"] is False
        assert result["result"]["current_gc"] == "gc1.example.com"

    def test_is_operation_healthy(self, manager, mock_client):
        """Test is_operation_healthy action operation."""
        mock_client.api.activedirectory.__getitem__.return_value.is_operation_healthy.post.return_value = {"healthy": True}

        result = manager.is_operation_healthy(1)

        assert result["changed"] is True  # POST operations change state
        assert result["result"]["healthy"] is True

    def test_change_machine_account_password(self, manager, mock_client):
        """Test change_machine_account_password action operation."""
        mock_client.api.activedirectory.__getitem__.return_value.change_machine_account_password.post.return_value = {
            "status": "success"
        }

        result = manager.change_machine_account_password(1)

        assert result["changed"] is True
        assert result["result"]["status"] == "success"

    def test_special_operation_error_handling(self, manager, mock_client):
        """Test error handling in special operations."""
        mock_client.api.activedirectory.__getitem__.return_value.refresh.patch.side_effect = Exception("API Error")

        with pytest.raises(VastAPIError, match="Failed to refresh"):
            manager.refresh(1)
