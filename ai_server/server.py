from flask import Flask, request, jsonify, abort
import ollama
import subprocess
import os
import requests
from typing import Optional
from dotenv import load_dotenv

from .redis_helper import REDIS_CONNECTION

# Load environment variables from .env file
load_dotenv()

app = Flask('AI server')

DEFAULT_MODEL = 'deepseek-coder-v2:latest'

# Llama.cpp configuration
LLAMA_CPP_CLI = '/data1/llama.cpp/bin/llama-cli'
GGUF_DIR = '/data1/GGUF'

# Llama server configuration - now uses environment variable
LLAMA_SERVER_URL = os.getenv('LLAMA_SERVER_URL')  # e.g., http://localhost:8080

# Known llama.cpp model in /data1/GGUF/
# We could add more models here if needed.
LLAMA_CPP_MODEL_DIRS = [
    'DeepSeek-V2.5-IQ1_M',
    'DeepSeek-V3-0324-UD-IQ2_XXS', 
    'DeepSeek-V3-0324-UD-Q2_K_XL'
]

# Output parsing skip patterns for llama-cli
LLAMA_CPP_SKIP_PATTERNS = [
    'ggml_cuda_init:', 'warning:', 'build:', 'main:', 'llama_model_loader:',
    'print_info:', 'load:', 'load_tensors:', 'llama_context:', 
    'common_init_from_params:', 'system_info:', 'sampler', 'generate:'
]


def chat_with_llama_server_http(model: str, content: str, timeout: int = 300) -> str:
    """Handle chat using llama-server HTTP API."""
    if not LLAMA_SERVER_URL:
        raise Exception("LLAMA_SERVER_URL environment variable not set")
    
    try:
        response = requests.post(
            f'{LLAMA_SERVER_URL}/v1/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': content}],
                'stream': False,
                'max_tokens': 512
            },
            headers={'Content-Type': 'application/json'},
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                raise Exception("Invalid response format from llama-server")
        else:
            response = requests.post(
                f'{LLAMA_SERVER_URL}/completion',
                json={
                    'prompt': content,
                    'n_predict': 512,
                    'stream': False
                },
                headers={'Content-Type': 'application/json'},
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('content', 'No response generated.')
            else:
                raise Exception(f"Llama-server HTTP error: {response.status_code} - {response.text}")
                
    except requests.Timeout:
        raise Exception(f"Llama-server request timed out for model {model}")
    except requests.RequestException as e:
        raise Exception(f"Llama-server request failed: {str(e)}")

def get_available_llamacpp_models():
    """Return list of available llama.cpp models."""
    models = []
    for model_dir in LLAMA_CPP_MODEL_DIRS:
        dir_path = os.path.join(GGUF_DIR, model_dir)
        if os.path.exists(dir_path):
            try:
                files = os.listdir(dir_path)
                for file in files:
                    if file.endswith('.gguf'):
                        models.append(f"{model_dir}/{file}")
            except Exception:
                continue
    return models

def resolve_model_path(model: str) -> Optional[str]:
    """Resolve model name to full GGUF file path."""
    for model_dir in LLAMA_CPP_MODEL_DIRS:
        dir_path = os.path.join(GGUF_DIR, model_dir)
        if not os.path.exists(dir_path):
            continue
            
        try:
            files = os.listdir(dir_path)
            gguf_files = [f for f in files if f.endswith('.gguf')]
            
            for file in gguf_files:
                if (model == model_dir or  # Directory name match
                    model == f"{model_dir}/{file}" or  # Full path match
                    model == file or  # Filename match
                    model == os.path.splitext(file)[0]):  # Name without extension
                    return os.path.join(dir_path, file)
        except Exception:
            continue
    
    return None

def is_llamacpp_available(model: str) -> bool:
    """Check if model is available in llama.cpp."""
    return resolve_model_path(model) is not None

def chat_with_ollama(model: str, content: str) -> str:
    """Handle chat using ollama."""
    response = ollama.chat(
        model=model,
        messages=[{'role': 'user', 'content': content}],
        stream=False
    )
    return response.message.content

def chat_with_llamacpp(model: str, content: str, timeout: int = 300) -> str:
    """Handle chat using llama.cpp CLI."""
    model_path = resolve_model_path(model)
    
    if not model_path:
        available_models = get_available_llamacpp_models()
        raise ValueError(f"Model not found: {model}. Available models: {available_models}")
    
    cmd = [
        LLAMA_CPP_CLI,
        '-m', model_path,
        '--n-gpu-layers', '40',
        '-p', content,
        '-n', '512',
        '--no-display-prompt',
        '-no-cnv'
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=False,
            timeout=timeout,
            check=True
        )
        
        # For V3 IQ1_M and IQ2_XXS models
        try:
            stdout_text = result.stdout.decode('utf-8')
        except UnicodeDecodeError:
            stdout_text = result.stdout.decode('utf-8', errors='replace')

        output_lines = stdout_text.strip().split('\n')
        response_lines = []
        for line in output_lines:
            if any(skip_pattern in line for skip_pattern in LLAMA_CPP_SKIP_PATTERNS):
                continue
            
            if line.startswith('llama_perf_'):
                break
                
            if line.strip():
                response_lines.append(line.strip())
        
        response = ' '.join(response_lines) if response_lines else ""
        return response if response else "No response generated."
        
    except subprocess.TimeoutExpired:
        raise Exception(f"Llama.cpp request timed out for model {model}")
    except subprocess.CalledProcessError as e:
        stderr_text = ""
        if e.stderr:
            try:
                stderr_text = e.stderr.decode('utf-8')
            except UnicodeDecodeError:
                stderr_text = e.stderr.decode('utf-8', errors='replace')
        raise Exception(f"Llama.cpp failed for {model}: {stderr_text.strip() if stderr_text else 'Unknown error'}")
    except FileNotFoundError:
        raise Exception("Llama.cpp CLI not found")

def chat_with_model(model: str, content: str, llama_mode: str = "cli") -> str:
    """Route chat request based on llama_mode: server (external), cli, or default fallback."""
    if llama_mode == "server":
        # Use external llama-server with fallbacks
        if not LLAMA_SERVER_URL:
            raise Exception("LLAMA_SERVER_URL environment variable not set for server mode")
        
        if is_llamacpp_available(model):
            try:
                return chat_with_llama_server_http(model, content)
            except Exception:
                # Fallback to llama-cli if server fails
                try:
                    return chat_with_llamacpp(model, content)
                except Exception:
                    # Final fallback to ollama
                    return chat_with_ollama(model, content)
        else:
            # Model not available in llama.cpp, use ollama
            return chat_with_ollama(model, content)
    
    elif llama_mode == "cli":
        if is_llamacpp_available(model):
            try:
                return chat_with_llamacpp(model, content)
            except Exception:
                # Fallback to ollama if llama-cli fails
                try:
                    return chat_with_ollama(model, content)
                except Exception as e_ollama:
                    available_llamacpp = get_available_llamacpp_models()
                    raise Exception(f"Model '{model}' failed in both llama-cli and ollama. "
                                   f"Available llama.cpp models: {available_llamacpp}. "
                                   f"Ollama error: {str(e_ollama)}")
        else:
            # Model not available in llama.cpp, try ollama
            try:
                return chat_with_ollama(model, content)
            except Exception as e:
                available_llamacpp = get_available_llamacpp_models()
                raise Exception(f"Model '{model}' not available in llama.cpp and failed in ollama. "
                               f"Available llama.cpp models: {available_llamacpp}. "
                               f"Ollama error: {str(e)}")
    
    else:
        # Default
        return chat_with_model(model, content, "cli")


def authenticate() -> str:
    """Authenticate the given request using an API key."""
    api_key = request.headers.get('X-API-KEY')
    if not api_key:
        abort(401, description="Missing API key")

    user = REDIS_CONNECTION.get(f"api-key:{api_key}")
    if not user:
        abort(401, description="Invalid API key")

    return user


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat request with optional llama_mode parameter."""
    authenticate()
    params = request.get_json()
    model = params.get('model', DEFAULT_MODEL)
    content = params.get('content', '')
    llama_mode = params.get('llama_mode', 'cli')
    
    if not content.strip():
        abort(400, description='Missing prompt content')

    try:
        response_content = chat_with_model(model, content, llama_mode)
        return jsonify(response_content)
        
    except Exception as e:
        abort(500, description=str(e))

@app.errorhandler(Exception)
def internal_error(error):
    return jsonify({"error": str(error)}), 500
