"""
api_utils.py

Contains utility functions for calling a local or remote LLM API endpoint.
Includes optional debug printing to help inspect the payload, prompt, and rolling memory.
"""
import json
import requests

def call_llm_api(url, payload, show_debug=False, history=None, prompt=None):
    """
    Sends a POST request to the LLM API with the given payload and returns the model's response.

    Args:
        url (str): The endpoint URL for the LLM API.
        payload (dict): The full JSON-ready API payload.
        show_debug (bool): Whether to print payload, prompt, and memory for debugging.
        history (list): Optional list of recent messages (role/content pairs).
        prompt (str): The raw prompt string (shown if debug is enabled).

    Returns:
        str: The LLM-generated reply, or an error string if the request fails.
    """
    headers = {"Content-Type": "application/json"}

    # Perform the POST request to the LLM API
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            # Return only the LLM's message content
            try:
                return response.json()["choices"][0]["message"]["content"]
            except (KeyError, ValueError, json.JSONDecodeError):
                return "[Error] Invalid API response format."
        else:
            return f"[Error {response.status_code}] {response.text}"
    except Exception as e:
        return f"[Connection Error] {e}"