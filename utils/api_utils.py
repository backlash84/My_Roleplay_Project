import json
import requests

def call_llm_api(url, payload, show_debug=False, history=None, prompt=None):
    """
    Sends a POST request to the LLM API with the given payload and returns the model's response.
    """
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            try:
                data = response.json()
            except (ValueError, json.JSONDecodeError):
                return "[Error] Invalid JSON in API response."

            # Try OpenAI-style chat format first
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                pass

            # Fallback: some servers return "text"
            try:
                return data["choices"][0]["text"]
            except (KeyError, IndexError, TypeError):
                return "[Error] Unrecognized API response format."
        else:
            return f"[Error {response.status_code}] {response.text}"
    except Exception as e:
        return f"[Connection Error] {e}"