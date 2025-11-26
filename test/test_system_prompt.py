from unittest.mock import MagicMock, patch

import pytest

TEST_MODEL = 'DeepSeek-V3-0324-UD-IQ2_XXS'
TEST_SYSTEM_PROMPT = "You are a helpful coding assistant."
TEST_USER_CONTENT = "Write a function"


class TestSystemPromptCore:
    """Core system prompt functionality tests."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        """Set up environment variables for each test."""
        monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379')

    @patch('markus_ai_server.server.subprocess.run')
    @patch('markus_ai_server.server.resolve_model_path')
    def test_llamacpp_cli_with_system_prompt(self, mock_resolve, mock_subprocess):
        """Test system_prompt passed to llama.cpp CLI."""
        from markus_ai_server.server import chat_with_llamacpp

        mock_resolve.return_value = f'/data1/GGUF/{TEST_MODEL}/{TEST_MODEL}.gguf'
        mock_result = MagicMock()
        mock_result.stdout = b'def function(): pass'
        mock_subprocess.return_value = mock_result

        chat_with_llamacpp(TEST_MODEL, TEST_USER_CONTENT, system_prompt=TEST_SYSTEM_PROMPT)

        args, kwargs = mock_subprocess.call_args
        cmd = args[0]
        assert '--system-prompt' in cmd
        assert TEST_SYSTEM_PROMPT in cmd

    @patch('markus_ai_server.server.requests.post')
    @patch('markus_ai_server.server.LLAMA_SERVER_URL', 'http://localhost:8080')
    def test_llama_server_http_with_system_prompt(self, mock_post):
        """Test system_prompt passed to llama-server HTTP."""
        from markus_ai_server.server import chat_with_llama_server_http

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': 'result'}}]}
        mock_post.return_value = mock_response

        chat_with_llama_server_http(TEST_MODEL, TEST_USER_CONTENT, system_prompt=TEST_SYSTEM_PROMPT)

        args, kwargs = mock_post.call_args
        messages = kwargs['json']['messages']
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == TEST_SYSTEM_PROMPT

    @patch('markus_ai_server.server.ollama.chat')
    def test_ollama_with_system_prompt(self, mock_ollama):
        """Test system_prompt passed to ollama."""
        from markus_ai_server.server import chat_with_ollama

        mock_response = MagicMock()
        mock_response.message.content = "result"
        mock_ollama.return_value = mock_response

        chat_with_ollama(TEST_MODEL, TEST_USER_CONTENT, system_prompt=TEST_SYSTEM_PROMPT)

        args, kwargs = mock_ollama.call_args
        messages = kwargs['messages']
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == TEST_SYSTEM_PROMPT

    @patch('markus_ai_server.server.chat_with_llamacpp')
    @patch('markus_ai_server.server.is_llamacpp_available')
    def test_chat_with_model_routing(self, mock_available, mock_chat):
        """Test system_prompt passed through chat_with_model routing."""
        from markus_ai_server.server import chat_with_model

        mock_available.return_value = True
        mock_chat.return_value = "result"

        chat_with_model(TEST_MODEL, TEST_USER_CONTENT, 'cli', TEST_SYSTEM_PROMPT)
        mock_chat.assert_called_once_with(
            TEST_MODEL,
            TEST_USER_CONTENT,
            system_prompt=TEST_SYSTEM_PROMPT,
            image_files=None,
            json_schema=None,
            model_options=None,
        )
