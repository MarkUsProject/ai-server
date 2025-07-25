import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')

from ai_server.server import chat_with_ollama, is_llamacpp_available, resolve_model_path

# Test models
TEST_LLAMACPP_MODEL = 'DeepSeek-V3-0324-UD-IQ2_XXS'
TEST_OLLAMA_MODEL = 'deepseek-coder-v2:latest'


@pytest.fixture
def mock_glob():
    """Mock glob.glob for model discovery tests."""
    with patch('ai_server.server.glob.glob') as mock:
        yield mock


@pytest.fixture
def mock_ollama():
    """Mock ollama.chat for ollama tests."""
    with patch('ai_server.server.ollama.chat') as mock:
        yield mock


class TestModelResolution:
    """Test core model resolution functionality."""

    def test_resolve_model_path_found(self, mock_glob):
        """Test model path resolution when model exists."""
        model_path = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'
        mock_glob.return_value = [model_path]

        result = resolve_model_path(TEST_LLAMACPP_MODEL)

        assert result == model_path
        mock_glob.assert_called_once_with(f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/*.gguf')

    def test_resolve_model_path_not_found(self, mock_glob):
        """Test model path resolution when model doesn't exist."""
        mock_glob.return_value = []

        result = resolve_model_path('nonexistent-model')

        assert result is None

    def test_is_llamacpp_available_true(self):
        """Test model availability check when model exists."""
        with patch('ai_server.server.resolve_model_path') as mock_resolve:
            mock_resolve.return_value = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'

            result = is_llamacpp_available(TEST_LLAMACPP_MODEL)

            assert result is True
            mock_resolve.assert_called_once_with(TEST_LLAMACPP_MODEL)

    def test_is_llamacpp_available_false(self):
        """Test model availability check when model doesn't exist."""
        with patch('ai_server.server.resolve_model_path') as mock_resolve:
            mock_resolve.return_value = None

            result = is_llamacpp_available('nonexistent-model')

            assert result is False


class TestOllamaCore:
    """Test core ollama functionality used as fallback."""

    def test_chat_with_ollama_success(self, mock_ollama):
        """Test successful chat with ollama."""
        mock_response = MagicMock()
        mock_response.message.content = "Hello! I'm DeepSeek Coder V2. I can help you with coding tasks."
        mock_ollama.return_value = mock_response

        result = chat_with_ollama(TEST_OLLAMA_MODEL, 'Help me write a Python function')

        assert result == "Hello! I'm DeepSeek Coder V2. I can help you with coding tasks."
        mock_ollama.assert_called_once_with(
            model=TEST_OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': 'Help me write a Python function'}],
            stream=False,
            options=None,
            format=None,
        )

    def test_chat_with_ollama_service_unavailable(self, mock_ollama):
        """Test ollama chat when service is unavailable."""
        mock_ollama.side_effect = Exception("Ollama service is not running")

        with pytest.raises(Exception, match="Ollama service is not running"):
            chat_with_ollama(TEST_OLLAMA_MODEL, 'Hello')

    def test_chat_with_ollama_model_not_found(self, mock_ollama):
        """Test ollama chat when model is not found."""
        mock_ollama.side_effect = Exception("model 'nonexistent:latest' not found")

        with pytest.raises(Exception, match="model 'nonexistent:latest' not found"):
            chat_with_ollama('nonexistent:latest', 'Hello')

    def test_chat_with_ollama_with_json_schema(self, mock_ollama, tmp_path):
        """Ollama chat should forward the JSON schema (format=…) when provided."""
        # Fake schema file
        test_schema = {"schema": {"type": "object", "properties": {"answer": {"type": "string"}}}}

        # Mock ollama response
        mock_response = MagicMock()
        mock_response.message.content = "42"
        mock_ollama.return_value = mock_response

        result = chat_with_ollama(TEST_OLLAMA_MODEL, "What is the meaning of life?", json_schema=test_schema, model_options=None)

        assert result == "42"
        mock_ollama.assert_called_once_with(
            model=TEST_OLLAMA_MODEL,
            messages=[{"role": "user", "content": "What is the meaning of life?"}],
            stream=False,
            format={'type': 'object', 'properties': {'answer': {'type': 'string'}}},
            options=None
        )
