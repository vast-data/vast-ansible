"""Unit tests for LdapsManager class.

Tests the business logic in the manager independently of Ansible.
"""

from unittest.mock import MagicMock

import pytest
from ansible_collections.vastdata.vms.plugins.module_utils.vast.errors import VastAPIError
from ansible_collections.vastdata.vms.plugins.module_utils.vast.managers.ldaps import LdapManager


class TestLdapsManager:
    """Test cases for LdapManager."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock VastClient."""
        client = MagicMock()
        client.api.ldaps = MagicMock()
        return client

    @pytest.fixture
    def manager(self, mock_client):
        """Create a LdapManager instance."""
        return LdapManager(mock_client, wait=False)

    def test_manager_initialization(self, manager):
        """Test manager is properly initialized."""
        assert manager.resource_name == "ldaps"
        assert manager.lookup_field == "domain_name"
        assert manager.wait is False

    def test_manager_async_flags(self, manager):
        """Test async operation flags are set correctly."""
        assert manager.async_create is False
        assert manager.async_update is False
        assert manager.async_delete is False

    def test_get_ldap_success(self, manager, mock_client):
        """Test getting an LDAP configuration."""
        # Mock API response
        mock_client.api.ldaps.get.return_value = [{"id": 1, "domain_name": "ldap.example.com"}]

        result = manager.get("ldap.example.com")

        assert result is not None
        assert result["domain_name"] == "ldap.example.com"
        mock_client.api.ldaps.get.assert_called_once_with(domain_name="ldap.example.com")

    def test_get_ldap_not_found(self, manager, mock_client):
        """Test getting non-existent LDAP returns None."""
        mock_client.api.ldaps.get.return_value = []

        result = manager.get("nonexistent.com")

        assert result is None

    def test_get_ldap_error(self, manager, mock_client):
        """Test API error is properly raised."""
        mock_client.api.ldaps.get.side_effect = Exception("API Error")

        with pytest.raises(VastAPIError, match="Failed to get ldaps"):
            manager.get("ldap.example.com")

    def test_create_ldap(self, manager, mock_client):
        """Test creating an LDAP configuration."""
        payload = {"domain_name": "ldap.example.com", "binddn": "cn=admin,dc=example,dc=com", "bindpw": "password"}
        mock_client.api.ldaps.post.return_value = {"id": 1, **payload}

        result = manager.create(payload)

        assert result["id"] == 1
        assert result["domain_name"] == "ldap.example.com"
        mock_client.api.ldaps.post.assert_called_once_with(**payload)

    def test_update_ldap(self, manager, mock_client):
        """Test updating an LDAP configuration."""
        patch_data = {"use_tls": True}
        mock_client.api.ldaps.__getitem__.return_value.patch.return_value = {
            "id": 1,
            "domain_name": "ldap.example.com",
            "use_tls": True,
        }

        result = manager.update(1, patch_data)

        assert result["use_tls"] is True
        mock_client.api.ldaps.__getitem__.assert_called_once_with(1)
        mock_client.api.ldaps.__getitem__.return_value.patch.assert_called_once_with(**patch_data)

    def test_delete_ldap(self, manager, mock_client):
        """Test deleting an LDAP configuration."""
        mock_client.api.ldaps.__getitem__.return_value.delete.return_value = {}

        result = manager.delete(1)

        assert result == {}
        mock_client.api.ldaps.__getitem__.assert_called_once_with(1)
        mock_client.api.ldaps.__getitem__.return_value.delete.assert_called_once()

    def test_compute_diff_no_changes(self, manager):
        """Test diff computation with no changes."""
        current = {"domain_name": "ldap.example.com", "port": 389}
        desired = {"domain_name": "ldap.example.com", "port": 389}

        patch = manager.compute_diff(current, desired)

        assert patch == {}

    def test_compute_diff_with_changes(self, manager):
        """Test diff computation with changes."""
        current = {"domain_name": "ldap.example.com", "port": 389}
        desired = {"domain_name": "ldap.example.com", "port": 636}

        patch = manager.compute_diff(current, desired)

        assert "port" in patch
        assert patch["port"] == 636

    def test_special_operation_set_posix_primary(self, manager, mock_client):
        """Test set_posix_primary special operation."""
        mock_client.api.ldaps.__getitem__.return_value.set_posix_primary.patch.return_value = {"status": "success"}

        result = manager.set_posix_primary(1)

        assert result["changed"] is True
        assert result["result"]["status"] == "success"
        mock_client.api.ldaps.__getitem__.assert_called_once_with(1)
