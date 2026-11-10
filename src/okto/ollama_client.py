import json
import sys
from functools import lru_cache
from pathlib import Path
try:
    import ollama
except ImportError:
    print("Error: 'ollama' library not found. Please run 'pip install ollama'.")
    sys.exit(1)

CONFIG_PATH = Path(".okto/config.json")
# Supports thinking mode, which /init turns on by default.
DEFAULT_MODEL = "qwen3:8b"

@lru_cache(maxsize=None)
def _supports_thinking(model: str) -> bool:
    """False only when Ollama lists the model's capabilities and "thinking" is not among them.

    If Ollama can't be asked (server down, model not pulled), returns True and lets
    generate() report the real error.
    """
    try:
        capabilities = ollama.show(model).capabilities
    except Exception:
        return True
    if capabilities is None:  # older Ollama servers don't report capabilities
        return True
    if "thinking" in capabilities:
        return True
    print(f"Note: model '{model}' does not support thinking; continuing without it. "
          f'Set "think": false in {CONFIG_PATH} to hide this note.')
    return False

def _get_config():
    """Reads the configuration from .okto/config.json."""
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found. Please run 'okto init' first.")
        sys.exit(1)
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: {CONFIG_PATH} is not a valid JSON file.")
        sys.exit(1)

def ask(prompt: str, think: bool = False) -> dict:
    """
    Sends a prompt to Ollama and returns a parsed JSON response.
    Expects Ollama to return a JSON string.
    """
    config = _get_config()
    orchestrator_config = config.get("orchestrator", {})
    model = orchestrator_config.get("model", DEFAULT_MODEL)
    if think and not _supports_thinking(model):
        think = False
    
    try:
        if think:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                stream=False,
                think=True
            )
        else:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                format="json",
                stream=False,
                think=False
            )
        
        response_text = response.response
        return json.loads(response_text)
        
    except ollama.ResponseError as e:
        print(f"Ollama Error: {e.error}")
        if e.status_code == 404:
            print(f"Hint: Model '{model}' not found. Try 'ollama pull {model}'.")
        sys.exit(1)
    except Exception as e:
        # Check if it's a connection error (httpx.ConnectError etc are common in newer versions)
        # The ollama lib uses httpx under the hood.
        error_msg = str(e).lower()
        if "connect" in error_msg or "connection" in error_msg:
            print("Error: Could not connect to Ollama. Is it running?")
            print("Make sure Ollama is installed and running on your system.")
        else:
            print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Simple isolation test
    print("Testing ollama_client in isolation...")
    test_prompt = "Return a JSON object with a 'status' field set to 'ok' and a 'message' field saying 'Hello from Okto'."
    result = ask(test_prompt)
    print(f"Result: {result}")
