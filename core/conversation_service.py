"""
conversation_service.py

Contains the ConversationService class, which encapsulates the logic for building prompts, payloads,
and conversation history used by the LLM backend. Keeps ChatView UI logic separate from model interaction logic.
"""

from utils.api_utils import call_llm_api
from utils.token_utils import count_tokens

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

    def build_prompt(self, user_message, memories, scenario, prefix, llm_character_config=None, user_character_config=None):
        """
        Constructs a full prompt string to send to the LLM. Combines:
        - Scenario (high-level context)
        - Prefix (persona rules or instructions)
        - Retrieved memories (from vector search)
        - The current user message
        """

        config = llm_character_config or {}
        llm_name = config.get("name", "Unnamed Character").strip()
        llm_info = config.get("character_information", "").strip()
        system_instructions = f"You are playing as this character:\nName: {llm_name}\n{llm_info.strip()}"

        user_config = user_character_config or {}
        user_name = user_config.get("name", "Player").strip()
        user_info = user_config.get("character_information", "").strip()
        user_instructions = f"The user is playing as this character:\nName: {user_name}\n{user_info.strip()}"

        system_prompt = f"{system_instructions}\n\n{user_instructions}"

        # === Token counting logic ===
        max_tokens = config.get("max_tokens", 4096)
        system_tokens = count_tokens(system_prompt)
        scenario_tokens = self.loaded_scenario_data.get("token_count", 0)
        prefix_tokens = self.loaded_prefix_data.get("token_count", 0)
        memory_tokens = sum(m.get("token_count", 0) for m in memory_chunks)

        overhead = system_tokens + scenario_tokens + prefix_tokens + memory_tokens
        available_for_rolling = max(0, max_tokens - overhead)

        # === Trim conversation history dynamically ===
        rolling_memory = []
        total = 0
        for msg in reversed(self.chat_history):
            tokens = count_tokens(msg.get("content", ""))
            if total + tokens > available_for_rolling:
                break
            rolling_memory.insert(0, msg)  # keep order
            total += tokens

        # Save to internal state (for debug view)
        self.trimmed_history = rolling_memory

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

    def build_chat_messages(self, conversation_history: list[dict], scenario: str, prefix: str, memories: str, llm_character_config: dict, user_character_config: dict) -> list[dict]:
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

        llm_name = llm_character_config.get("name", "Unknown Character")
        llm_info = llm_character_config.get("character_information", "").strip()

        user_name = user_character_config.get("name", "Unknown Player")
        user_info = user_character_config.get("character_information", "").strip()

        system_content = f"""You are playing as this character:
        Name: {llm_name}
        Character Information:
        {llm_info}

        The user is playing as this character:
        Name: {user_name}
        Character Information:
        {user_info}

        {scenario.strip()}

        {prefix.strip()}
        {formatted_memories}"""
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