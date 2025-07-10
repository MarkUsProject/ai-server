from unittest.mock import patch

import pytest

TEST_MODEL = 'DeepSeek-V3-0324-UD-IQ2_XXS'
TEST_SYSTEM_PROMPT = "You are a helpful coding assistant."
TEST_USER_CONTENT = "Write a function"


class TestSystemPromptAPI:
    """Test /chat API endpoint with system_prompt functionality."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up environment variables for each test."""
        monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379')

    @pytest.fixture
    def client(self):
        """Create test client for Flask app."""
        from ai_server.server import app

        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    @patch('ai_server.server.REDIS_CONNECTION')
    @patch('ai_server.server.chat_with_model')
    def test_api_with_system_prompt(self, mock_chat, mock_redis, client):
        """Test /chat endpoint receives and passes system_prompt."""
        mock_redis.get.return_value = b'test_user'
        mock_chat.return_value = "def function(): pass"

        response = client.post(
            '/chat',
            headers={'X-API-KEY': 'test-key'},
            data={'model': TEST_MODEL, 'content': TEST_USER_CONTENT, 'system_prompt': TEST_SYSTEM_PROMPT},
        )

        assert response.status_code == 200

        mock_chat.assert_called_once_with(TEST_MODEL, TEST_USER_CONTENT, 'cli', TEST_SYSTEM_PROMPT, [], None)

    @patch('ai_server.server.REDIS_CONNECTION')
    @patch('ai_server.server.chat_with_model')
    def test_api_without_system_prompt(self, mock_chat, mock_redis, client):
        """Test /chat endpoint works without system_prompt."""
        mock_redis.get.return_value = b'test_user'
        mock_chat.return_value = "def function(): pass"

        response = client.post(
            '/chat', headers={'X-API-KEY': 'test-key'}, data={'model': TEST_MODEL, 'content': TEST_USER_CONTENT}
        )

        assert response.status_code == 200

        mock_chat.assert_called_once_with(TEST_MODEL, TEST_USER_CONTENT, 'cli', None, [], None)

    @patch('ai_server.server.REDIS_CONNECTION')
    def test_api_authentication_still_required(self, mock_redis, client):
        """Test that authentication is still required with system_prompt."""
        mock_redis.get.return_value = None

        response = client.post(
            '/chat',
            headers={'X-API-KEY': 'invalid-key'},
            data={'model': TEST_MODEL, 'content': TEST_USER_CONTENT, 'system_prompt': TEST_SYSTEM_PROMPT},
        )

        assert response.status_code == 500
        response_data = response.get_json()
        assert "401 Unauthorized" in response_data['error']
