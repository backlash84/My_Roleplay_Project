"""
conversation_service.py

Contains the ConversationService class, which encapsulates the logic for building prompts, payloads,
and conversation history used by the LLM backend. Keeps ChatView UI logic separate from model interaction logic.
"""

from utils.api_utils import call_llm_api

class ConversationService:
    """
    A service layer that handles prompt and payload construction for LLM interactions.
    Decouples LLM logic from UI (ChatView) for cleaner architecture.
    """
    def __init__(self, controller):
        """
        Initialize with a reference to the main controller (RoleplayApp), allowing access
        to UI settings and shared data like memory chunk limits or similarity thresholds.
        """
        self.controller = controller

    def build_prompt(self, user_message, retrieved_memories, scenario, prefix):
        """
        Constructs a full prompt string to send to the LLM. Combines:
        - Scenario (high-level context)
        - Prefix (persona rules or instructions)
        - Retrieved memories (from vector search)
        - The current user message
        """
        memory_snippets = "\n\n".join(
            m.get("prompt_text", "").strip() for m in retrieved_memories if m.get("prompt_text")
        )

        return f"{scenario.strip()}\n\n{prefix.strip()}\n\n{memory_snippets}\n\nUser: {user_message.strip()}"

    def build_payload(self, prompt, settings_data):
        """
        Builds the API payload for the LLM from current settings.

        Includes model type, generation parameters (temperature, penalties),
        and vector memory retrieval settings (top_k, similarity_threshold).
        Optionally includes max_tokens if a valid number is set.
        """

        payload = {
            "model": settings_data.get("model"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings_data.get("temperature", 0.7),
            "frequency_penalty": settings_data.get("frequency_penalty", 0.0),
            "presence_penalty": settings_data.get("presence_penalty", 0.0),
            "top_k": settings_data.get("top_k", 10),
            "similarity_threshold": settings_data.get("similarity_threshold", 0.7)
        }

        try:  # Ensure max_tokens is numeric and positive before including
            max_tokens = settings_data.get("max_tokens")
            if isinstance(max_tokens, int) and max_tokens > 0:
                payload["max_tokens"] = max_tokens
        except (ValueError, TypeError):
            pass

        return payload

    def build_chat_messages(self, conversation_history: list[dict], scenario: str, prefix: str, memories: str) -> list[dict]:
        """
        Builds the chat message list for the LLM, starting with a system prompt that includes
        the scenario, prefix, and memory.

        Returns:
            list of dicts: List of chat messages with roles.
        """
        settings = self.controller.frames["AdvancedSettings"]
        history_limit = settings.get_chat_history_length()

        messages = []

        # Add system message with full context
        formatted_memories = ""
        for mem in memories:
            text = mem.get("prompt_text", "").strip()
            if text:
                formatted_memories += f"- {text}\n"
        if formatted_memories:
            formatted_memories = f"\n--- Retrieved Memories ---\n{formatted_memories.strip()}"

        system_content = f"{scenario.strip()}\n\n{prefix.strip()}{formatted_memories}"
        messages.append({"role": "system", "content": system_content})

        
        # Add limited chat history
        if history_limit <= 0:
            recent_history = []
        else:
            recent_history = conversation_history[-history_limit:]

        for entry in recent_history:
            role = entry.get("role")
            content = entry.get("content")
            if role and content:
                messages.append({"role": role, "content": content})

        return messages, recent_history

    def fetch_reply(self, payload, conversation_history, prompt, debug_mode=False):
        """
        Sends the LLM payload to the configured endpoint and returns the generated reply.

        Args:
            payload: JSON-ready request to the LLM API.
            conversation_history: List of recent messages for context (if supported).
            prompt: The final combined prompt (used for fallback debugging).
            debug_mode: Whether to enable verbose API logging.
        """
        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        return call_llm_api(url, payload, debug_mode, conversation_history, prompt)