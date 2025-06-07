#!/usr/bin/env python3
"""
Test script for AI server ollama/llama.cpp integration.
"""

import sys
import os

os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ai_server'))

from ai_server.server import (
    is_llamacpp_available, 
    chat_with_llamacpp, 
    chat_with_ollama,
    get_available_llamacpp_models,
    LLAMA_CPP_MODEL_DIRS
)

def test_model_with_llamacpp(models, prompt, description_prefix="", timeout=300):
    """
    Helper function to test one or more models with llama.cpp.
    
    Args:
        models: List of model names or single model name
        prompt: The prompt to test with
        description_prefix: Optional prefix for log messages
        timeout: Timeout for llama.cpp calls
    """
    if isinstance(models, str):
        models = [models]
        
    for test_model in models:
        model_desc = f"{description_prefix}{test_model}" if description_prefix else test_model
        print(f"\nTesting model: {model_desc}")
        
        if is_llamacpp_available(test_model):
            print("Model detected as available in llama.cpp")
            
            try:
                print("Calling llama.cpp...")
                response = chat_with_llamacpp(test_model, prompt, timeout=timeout)
                
                print("Llama.cpp integration successful!")
                print(f"Response: {response}")
                
            except Exception as e:
                print(f"Llama.cpp integration failed: {e}")
        else:
            print("Model not detected in llama.cpp")

def test_model_detection():
    """Test the model detection logic."""
    print("Testing Model Detection")
    
    test_cases = [
        # Should use llama.cpp (based on hardcoded directories)
        ("DeepSeek-V2.5-IQ1_M", True),
        ("DeepSeek-V3-0324-UD-IQ2_XXS", True),
        ("DeepSeek-V3-0324-UD-Q2_K_XL", True),
        ("outfile", True),
        ("outfile.gguf", True),
        ("DeepSeek-V2.5-IQ1_M/outfile.gguf", True),
        
        # Should fallback to ollama (not in hardcoded list)
        ("deepseek-coder-v2:latest", False),
        ("llava:34b", False),
        ("nonexistent-model", False),
    ]
    
    for model, expected in test_cases:
        result = is_llamacpp_available(model)
        status = "PASS" if result == expected else "FAIL"
        backend = "llama.cpp" if result else "ollama fallback"
        print(f"{status}: {model} -> {backend}")
    print()

def test_available_models():
    """Test that llama.cpp models are available."""
    print("Testing Available Models")
    
    print(f"Model directories: {LLAMA_CPP_MODEL_DIRS}")
    
    available_models = get_available_llamacpp_models()
    print(f"Available llama.cpp models: {available_models}")
    
    for model_dir in LLAMA_CPP_MODEL_DIRS:
        dir_path = f"/data1/GGUF/{model_dir}"
        exists = os.path.exists(dir_path)
        status = "FOUND" if exists else "MISSING"
        print(f"{status}: {model_dir} -> {dir_path}")
    print()

def test_llamacpp_integration():
    """Test llama.cpp integration with simple model names."""
    print("Testing Llama.cpp Integration")
    
    # Try different ways to reference the same model
    test_cases = [
        "outfile",  # Just filename without extension
        "outfile.gguf",  # Filename with extension
        "DeepSeek-V2.5-IQ1_M",  # Directory name
    ]
    
    test_prompt = "Hello, respond with just 'Test successful'"
    
    test_model_with_llamacpp(test_cases, test_prompt)

def test_ollama_fallback():
    """Test ollama fallback for models not in llama.cpp."""
    print("Testing Ollama Fallback")
    
    test_model = "deepseek-coder-v2:latest"
    test_prompt = "Hello, respond with just 'Ollama works'"
    
    print(f"Testing model: {test_model}")
    print(f"Should NOT be available in llama.cpp: {not is_llamacpp_available(test_model)}")
    
    try:
        print("Calling ollama...")
        response = chat_with_ollama(test_model, test_prompt)
        
        print("Ollama integration successful!")
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"Ollama integration failed: {e}")
    print()

def test_v3_models():
    """Test V3 model integration (these are large models that may fail due to resource constraints)."""
    print("Testing V3 Models (Large Models)")
    
    v3_models = [
        "DeepSeek-V3-0324-UD-IQ2_XXS",
        "DeepSeek-V3-0324-UD-Q2_K_XL", 
    ]
    
    test_prompt = "Hello, respond with just 'V3 Test successful'"
    
    test_model_with_llamacpp(v3_models, test_prompt, "V3 Model: ")

def test_model_quality():
    """Test model quality with meaningful questions."""
    print("Testing Model Quality with Real Questions")
    
    test_questions = [
        "What is Python?",
        "Explain recursion in programming",
    ]
    
    simple_questions = [
        "What is recursion?", 
        "Why use Git?"
    ]
    
    # Test models in order of size/capability
    test_models = [
        ("DeepSeek-V2.5-IQ1_M", "V2.5 (52GB)"),
        ("DeepSeek-V3-0324-UD-IQ2_XXS", "V3-IQ2_XXS (218GB)"),
        ("DeepSeek-V3-0324-UD-Q2_K_XL", "V3-Q2_K_XL (247GB)")
    ]
    
    for question in test_questions:
        print(f"\nQuestion: {question}")
        
        for model, description in test_models:
            test_model_with_llamacpp([model], question, f"[{description}] ", timeout=600)

def test_error_handling():
    """Test error handling for invalid models."""
    print("Testing Error Handling")
    
    try:
        # Test invalid llama.cpp model
        chat_with_llamacpp("nonexistent-model", "test")
        print("FAIL: Should have raised error for invalid model")
    except ValueError as e:
        print(f"PASS: Correctly caught invalid model error: {e}")
    except Exception as e:
        print(f"FAIL: Unexpected error type: {e}")
    print()

def main():
    """Run all tests."""
    print("AI Server Integration Tests")
    
    print("Model detection")
    test_model_detection()
    test_available_models()
    test_error_handling()
    
    print("Integration tests")
    test_llamacpp_integration()
    test_ollama_fallback()
    test_v3_models()

    print("Model quality")
    test_model_quality()

    print("Tests completed!")

if __name__ == "__main__":
    main() 
