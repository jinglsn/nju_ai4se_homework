import pytest
from unittest.mock import patch
from src.config.keyring import set_api_key, get_api_key, clear_api_key, key_status

SERVICE_NAME = "harness-test"


@patch("src.config.keyring.keyring")
class TestKeyring:
    def test_set_and_get_api_key(self, mock_keyring):
        mock_keyring.get_password.return_value = "test-key-123"
        set_api_key(SERVICE_NAME, "test-key-123")
        mock_keyring.set_password.assert_called_once()
        assert get_api_key(SERVICE_NAME) == "test-key-123"

    def test_key_status_configured(self, mock_keyring):
        mock_keyring.get_password.return_value = "some-key"
        status = key_status(SERVICE_NAME)
        assert status == "configured"

    def test_key_status_not_configured(self, mock_keyring):
        mock_keyring.get_password.return_value = None
        status = key_status(SERVICE_NAME)
        assert status == "not configured"

    def test_clear_api_key(self, mock_keyring):
        clear_api_key(SERVICE_NAME)
        mock_keyring.delete_password.assert_called_once()

    def test_get_api_key_returns_none_when_missing(self, mock_keyring):
        mock_keyring.get_password.return_value = None
        assert get_api_key(SERVICE_NAME) is None