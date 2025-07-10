import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')

from ai_server.server import chat_with_llamacpp, chat_with_model

# Test models
TEST_LLAMACPP_MODEL = 'DeepSeek-V3-0324-UD-IQ2_XXS'
TEST_OLLAMA_MODEL = 'deepseek-coder-v2:latest'


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for CLI tests."""
    with patch('ai_server.server.subprocess.run') as mock:
        yield mock


@pytest.fixture
def mock_resolve_model_path():
    """Mock resolve_model_path for CLI tests."""
    with patch('ai_server.server.resolve_model_path') as mock:
        yield mock


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


class TestLlamaCppCLI:
    """Test llama.cpp CLI execution."""

    def test_chat_with_llamacpp_success(self, mock_resolve_model_path, mock_subprocess):
        """Test successful CLI chat with llama.cpp."""
        model_path = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'
        mock_resolve_model_path.return_value = model_path

        mock_result = MagicMock()
        mock_result.stdout = b'I can help you with DeepSeek V3.'
        mock_subprocess.return_value = mock_result

        result = chat_with_llamacpp(TEST_LLAMACPP_MODEL, 'Hello, can you help me code?')

        assert result == "I can help you with DeepSeek V3."
        mock_resolve_model_path.assert_called_once_with(TEST_LLAMACPP_MODEL)

        # Verify correct CLI command structure
        args, kwargs = mock_subprocess.call_args
        cmd = args[0]
        assert '/data1/llama.cpp/bin/llama-cli' in cmd
        assert '-m' in cmd and model_path in cmd
        assert '--n-gpu-layers' in cmd and '40' in cmd
        assert '--single-turn' in cmd

    def test_chat_with_llamacpp_model_not_found(self, mock_resolve_model_path):
        """Test CLI chat when model is not found."""
        mock_resolve_model_path.return_value = None

        with pytest.raises(ValueError, match="Model not found: nonexistent-model"):
            chat_with_llamacpp('nonexistent-model', 'Hello')

    def test_chat_with_llamacpp_subprocess_error(self, mock_resolve_model_path, mock_subprocess):
        """Test CLI chat when subprocess fails."""
        mock_resolve_model_path.return_value = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'

        error = subprocess.CalledProcessError(1, 'cmd')
        error.stderr = b'CUDA out of memory'
        mock_subprocess.side_effect = error

        with pytest.raises(Exception, match=f"Llama.cpp failed for {TEST_LLAMACPP_MODEL}: CUDA out of memory"):
            chat_with_llamacpp(TEST_LLAMACPP_MODEL, 'Hello')


class TestCLIModeRouting:
    """Test CLI mode routing and fallback logic."""

    @pytest.fixture(autouse=True)
    def setup_routing_mocks(self):
        """Set up common mocks for routing tests."""
        with patch('ai_server.server.chat_with_llamacpp') as mock_chat_llamacpp, patch(
            'ai_server.server.is_llamacpp_available'
        ) as mock_available, patch('ai_server.server.chat_with_ollama') as mock_chat_ollama:
            self.mock_chat_llamacpp = mock_chat_llamacpp
            self.mock_available = mock_available
            self.mock_chat_ollama = mock_chat_ollama
            yield

    def test_cli_mode_uses_llamacpp_when_available(self):
        """Test CLI mode routes to llama.cpp when model is available."""
        self.mock_available.return_value = True
        self.mock_chat_llamacpp.return_value = "CLI response from DeepSeek V3"

        result = chat_with_model(TEST_LLAMACPP_MODEL, 'Write a function', llama_mode='cli')

        assert result == "CLI response from DeepSeek V3"
        self.mock_available.assert_called_once_with(TEST_LLAMACPP_MODEL)
        self.mock_chat_llamacpp.assert_called_once_with(TEST_LLAMACPP_MODEL, 'Write a function', system_prompt=None, image_files=None, json_schema=None)

    def test_cli_mode_fallback_to_ollama_when_unavailable(self):
        """Test CLI mode falls back to ollama when model not available in llama.cpp."""
        self.mock_available.return_value = False
        self.mock_chat_ollama.return_value = "Ollama response from DeepSeek Coder"

        result = chat_with_model(TEST_OLLAMA_MODEL, 'Help with coding', llama_mode='cli')

        assert result == "Ollama response from DeepSeek Coder"
        self.mock_available.assert_called_once_with(TEST_OLLAMA_MODEL)
        self.mock_chat_ollama.assert_called_once_with(TEST_OLLAMA_MODEL, 'Help with coding', system_prompt=None, image_files=None, json_schema=None)

    def test_default_mode_is_cli(self):
        """Test that default mode is CLI when no llama_mode specified."""
        self.mock_available.return_value = True
        self.mock_chat_llamacpp.return_value = "Default CLI mode response"

        result = chat_with_model(TEST_LLAMACPP_MODEL, 'Help me')  # No llama_mode specified

        assert result == "Default CLI mode response"
        self.mock_available.assert_called_once_with(TEST_LLAMACPP_MODEL)
        self.mock_chat_llamacpp.assert_called_once_with(TEST_LLAMACPP_MODEL, 'Help me', system_prompt=None, image_files=None, json_schema=None)


class TestCLIModeIntegration:
    """Test complete CLI mode integration flows."""

    def test_complete_cli_flow_with_real_model(self, mock_glob, mock_subprocess):
        """Test complete CLI flow: model resolution → CLI execution."""
        model_path = f'/data1/GGUF/{TEST_LLAMACPP_MODEL}/{TEST_LLAMACPP_MODEL}.gguf'

        mock_glob.return_value = [model_path]
        mock_result = MagicMock()
        mock_result.stdout = b'Complete integration test successful with DeepSeek V3!'
        mock_subprocess.return_value = mock_result

        result = chat_with_model(TEST_LLAMACPP_MODEL, 'Integration test', llama_mode='cli')

        assert result == "Complete integration test successful with DeepSeek V3!"
        # Verify glob called twice: once for availability check, once for CLI execution
        assert mock_glob.call_count == 2
        mock_subprocess.assert_called_once()

    def test_complete_cli_fallback_flow_to_ollama(self, mock_glob, mock_ollama):
        """Test complete CLI fallback flow: model not found → fallback to ollama."""
        # Mock model not found in llama.cpp
        mock_glob.return_value = []

        # Mock successful ollama response
        mock_response = MagicMock()
        mock_response.message.content = "Ollama CLI fallback integration test successful!"
        mock_ollama.return_value = mock_response

        result = chat_with_model(TEST_OLLAMA_MODEL, 'Fallback test', llama_mode='cli')

        assert result == "Ollama CLI fallback integration test successful!"
        mock_glob.assert_called_once_with(f'/data1/GGUF/{TEST_OLLAMA_MODEL}/*.gguf')
        mock_ollama.assert_called_once()

    def test_cli_mode_passes_json_schema_to_ollama(self, tmp_path):
        """
        When json_schema is supplied, chat_with_model should forward the parsed
        schema (as a dict) to chat_with_ollama.
        """
        test_schema = {"schema": {"type":"object","properties":{"answer":{"type":"string"}}}}

        #  Prepare mocks
        with patch('ai_server.server.is_llamacpp_available', return_value=False), \
             patch('ai_server.server.chat_with_ollama') as mock_ollama:
            mock_ollama.return_value = "schema-aware response"

            result = chat_with_model(
                TEST_OLLAMA_MODEL,
                "Give me an answer",
                llama_mode='cli',
                json_schema=test_schema
            )

            assert result == "schema-aware response"

            mock_ollama.assert_called_once_with(
                TEST_OLLAMA_MODEL,
                "Give me an answer",
                system_prompt=None,
                image_files=None,
                json_schema=test_schema
            )
