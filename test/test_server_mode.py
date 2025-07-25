import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')

from ai_server.server import chat_with_llama_server_http, chat_with_model

# Test models
TEST_LLAMACPP_MODEL = 'DeepSeek-V3-0324-UD-IQ2_XXS'
TEST_OLLAMA_MODEL = 'deepseek-coder-v2:latest'


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for HTTP tests."""
    with patch('ai_server.server.requests.post') as mock:
        yield mock


@pytest.fixture
def mock_llama_server_url():
    """Mock LLAMA_SERVER_URL for server tests."""
    with patch('ai_server.server.LLAMA_SERVER_URL', 'http://localhost:8080'):
        yield


@pytest.fixture
def mock_glob():
    """Mock glob.glob for model discovery tests."""
    with patch('ai_server.server.glob.glob') as mock:
        yield mock


@pytest.fixture
def mock_ollama():
    """Mock ollama.chat for fallback tests."""
    with patch('ai_server.server.ollama.chat') as mock:
        yield mock


class TestLlamaServerHTTP:
    """Test llama.cpp server HTTP functionality."""

    def test_chat_with_llama_server_http_success(self, mock_requests_post, mock_llama_server_url):
        """Test successful HTTP chat with llama-server."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': 'Server response from DeepSeek V3'}}]}
        mock_requests_post.return_value = mock_response

        result = chat_with_llama_server_http(TEST_LLAMACPP_MODEL, 'Hello from server')

        assert result == "Server response from DeepSeek V3"

        # Verify correct API call
        args, kwargs = mock_requests_post.call_args
        assert args[0] == 'http://localhost:8080/v1/chat/completions'
        assert kwargs['json']['model'] == TEST_LLAMACPP_MODEL
        assert kwargs['json']['messages'][0]['content'] == 'Hello from server'

    def test_chat_with_llama_server_http_no_url(self):
        """Test HTTP chat when LLAMA_SERVER_URL is not set."""
        with patch('ai_server.server.LLAMA_SERVER_URL', None):
            with pytest.raises(Exception, match="LLAMA_SERVER_URL environment variable not set"):
                chat_with_llama_server_http(TEST_LLAMACPP_MODEL, 'Hello')

    def test_chat_with_llama_server_http_error_response(self, mock_requests_post, mock_llama_server_url):
        """Test HTTP chat when server returns error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_requests_post.return_value = mock_response

        with pytest.raises(Exception, match="Llama-server HTTP error"):
            chat_with_llama_server_http(TEST_LLAMACPP_MODEL, 'Hello')

    def test_chat_with_llama_server_http_invalid_response_format(self, mock_requests_post, mock_llama_server_url):
        """Test HTTP chat when server returns invalid response format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'error': 'Invalid request'}  # Missing choices
        mock_requests_post.return_value = mock_response

        with pytest.raises(Exception, match="Invalid response format from llama-server"):
            chat_with_llama_server_http(TEST_LLAMACPP_MODEL, 'Hello')


class TestServerModeRouting:
    """Test server mode routing and fallback logic."""

    @pytest.fixture(autouse=True)
    def setup_routing_mocks(self):
        """Set up common mocks for routing tests."""
        with patch('ai_server.server.chat_with_llama_server_http') as mock_chat_server, patch(
            'ai_server.server.is_llamacpp_available'
        ) as mock_available, patch('ai_server.server.chat_with_ollama') as mock_chat_ollama, patch(
            'ai_server.server.LLAMA_SERVER_URL', 'http://localhost:8080'
        ):
            self.mock_chat_server = mock_chat_server
            self.mock_available = mock_available
            self.mock_chat_ollama = mock_chat_ollama
            yield

    def test_server_mode_uses_llamacpp_when_available(self):
        """Test server mode routes to llama-server when model is available."""
        self.mock_available.return_value = True
        self.mock_chat_server.return_value = "Server response from DeepSeek V3"

        result = chat_with_model(TEST_LLAMACPP_MODEL, 'Explain code', llama_mode='server')

        assert result == "Server response from DeepSeek V3"
        self.mock_available.assert_called_once_with(TEST_LLAMACPP_MODEL)
        self.mock_chat_server.assert_called_once_with(TEST_LLAMACPP_MODEL, 'Explain code', system_prompt=None, image_files=None, model_options=None)

    def test_server_mode_fallback_to_ollama_when_unavailable(self):
        """Test server mode falls back to ollama when model not available in llama.cpp."""
        self.mock_available.return_value = False
        self.mock_chat_ollama.return_value = "Ollama fallback response"

        result = chat_with_model(TEST_OLLAMA_MODEL, 'Debug code', llama_mode='server')

        assert result == "Ollama fallback response"
        self.mock_available.assert_called_once_with(TEST_OLLAMA_MODEL)
        self.mock_chat_ollama.assert_called_once_with(TEST_OLLAMA_MODEL, 'Debug code', system_prompt=None, image_files=None, model_options=None)

    def test_server_mode_fallback_to_ollama_with_model_options(self):
        """Test server mode falls back to ollama and passes model_options correctly when model is unavailable in llama.cpp."""
        self.mock_available.return_value = False
        self.mock_chat_ollama.return_value = "Ollama fallback response"

        test_options = {"temperature": 0.3, "top_k": 50}

        result = chat_with_model(
            TEST_OLLAMA_MODEL,
            'Debug code',
            llama_mode='server',
            model_options=test_options
        )

        assert result == "Ollama fallback response"
        self.mock_available.assert_called_once_with(TEST_OLLAMA_MODEL)
        self.mock_chat_ollama.assert_called_once_with(
            TEST_OLLAMA_MODEL,
            'Debug code',
            system_prompt=None,
            image_files=None,
            model_options=test_options
        )

    def test_server_mode_requires_server_url(self):
        """Test server mode requires LLAMA_SERVER_URL to be set."""
        with patch('ai_server.server.LLAMA_SERVER_URL', None):
            self.mock_available.return_value = True

            with pytest.raises(Exception, match="LLAMA_SERVER_URL environment variable not set"):
                chat_with_model(TEST_LLAMACPP_MODEL, 'Hello', llama_mode='server')

    def test_invalid_llama_mode_raises_error(self):
        """Test that invalid llama_mode raises ValueError."""
        self.mock_available.return_value = True

        with pytest.raises(ValueError, match="Invalid llama_mode: 'invalid'"):
            chat_with_model(TEST_LLAMACPP_MODEL, 'Hello', llama_mode='invalid')


class TestServerModeIntegration:
    """Test complete server mode integration flows."""

    def test_complete_server_flow_with_real_model(self, mock_glob, mock_requests_post, mock_llama_server_url):
        """Test complete server flow: model resolution → HTTP API call."""
        model_path = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'

        # Mock model found (only checked once for availability in server mode)
        mock_glob.return_value = [model_path]

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': 'Server integration test successful!'}}]}
        mock_requests_post.return_value = mock_response

        result = chat_with_model(TEST_LLAMACPP_MODEL, 'Integration test', llama_mode='server')

        assert result == "Server integration test successful!"
        # In server mode, glob.glob only called once for is_llamacpp_available
        mock_glob.assert_called_once_with(f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/*.gguf')
        mock_requests_post.assert_called_once()

    def test_complete_server_fallback_flow_to_ollama(self, mock_glob, mock_ollama, mock_llama_server_url):
        """Test complete server fallback flow: model not found → fallback to ollama."""
        # Mock model not found in llama.cpp
        mock_glob.return_value = []

        # Mock successful ollama response
        mock_response = MagicMock()
        mock_response.message.content = "Ollama server fallback integration test successful!"
        mock_ollama.return_value = mock_response

        result = chat_with_model(TEST_OLLAMA_MODEL, 'Fallback test', llama_mode='server')

        assert result == "Ollama server fallback integration test successful!"
        mock_glob.assert_called_once_with(f'/data1/GGUF/{TEST_OLLAMA_MODEL}/*.gguf')
        mock_ollama.assert_called_once()
