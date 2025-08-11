"""
conversation_service.py (modified version)

Contains the ConversationService class, which encapsulates the logic for
building prompts, payloads, and conversation history used by the LLM backend.
This version introduces a dynamic, token-budget aware rolling memory system...
"""

from utils.api_utils import call_llm_api
from utils.token_utils import count_tokens

class ConversationService:
    """Service layer for building prompts and payloads for the LLM."""
    DEFAULT_CONTEXT_TOKEN_BUDGET = 16000

    def __init__(self, controller):
        self.controller = controller
        self.loaded_scenario_data = {}
        self.loaded_prefix_data = {}
        self.trimmed_history = []

    def _build_system_message(self, scenario, prefix, memories,
                          llm_character_config, user_character_config) -> str:
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

        system_content = (
            f"You are playing as this character:\n"
            f"Name: {llm_name}\n"
            f"Character Information:\n{llm_info}\n\n"
            f"The user is playing as this character:\n"
            f"Name: {user_name}\n"
            f"Character Information:\n{user_info}\n\n"
            f"{scenario.strip()}\n\n"
            f"{prefix.strip()}"
        )

        system_content += formatted_memories
        return system_content

    def _calculate_overhead_tokens(self, system_message: str,
                                   buffer_tokens: int = 50) -> int:
        return count_tokens(system_message) + buffer_tokens

    def build_payload(self, prompt: str, settings_data: dict) -> dict:
        payload = {
            "model": settings_data.get("model"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings_data.get("temperature", 0.7),
            "frequency_penalty": settings_data.get("frequency_penalty", 0.0),
            "presence_penalty": settings_data.get("presence_penalty", 0.0),
        }

        top_p = settings_data.get("top_p")
        if isinstance(top_p, (int, float)):
            payload["top_p"] = float(top_p)

        try:
            max_tokens = settings_data.get("max_tokens")
            if isinstance(max_tokens, int) and max_tokens > 0:
                payload["max_tokens"] = max_tokens
        except (ValueError, TypeError):
            pass

        stops = settings_data.get("stop", [])
        if isinstance(stops, (list, tuple)) and all(isinstance(s, str) for s in stops):
            payload["stop"] = list(stops)

        stream = settings_data.get("stream", False)
        if isinstance(stream, bool):
            payload["stream"] = stream

        return payload

    def fetch_reply(self, payload, conversation_history, prompt, debug_mode=False):
        # Forward request to the LLM API.
        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        return call_llm_api(url, payload, debug_mode, conversation_history, prompt)

    def build_prompt(self, user_message, memories, scenario, prefix,
                        conversation_history,
                        llm_character_config=None, user_character_config=None) -> str:
        config = llm_character_config or {}
        llm_name = config.get("name", "Unnamed Character").strip()
        llm_info = config.get("character_information", "").strip()
        user_config = user_character_config or {}
        user_name = user_config.get("name", "Player").strip()
        user_info = user_config.get("character_information", "").strip()

        system_instructions = (
            f"You are playing as this character:\n"
            f"Name: {llm_name}\n"
            f"{llm_info}"
        )
        user_instructions = (
            f"The user is playing as this character:\n"
            f"Name: {user_name}\n"
            f"{user_info}"
        )
        system_prompt = f"{system_instructions}\n\n{user_instructions}"

        # Use Advanced Settings token budget (not character config)
        max_tokens = self.DEFAULT_CONTEXT_TOKEN_BUDGET
        settings_frame = self.controller.frames.get("AdvancedSettings")
        if settings_frame and hasattr(settings_frame, "get_max_tokens"):
            try:
                mt = settings_frame.get_max_tokens()  # may be None if "No Token Limit" is enabled
                if isinstance(mt, int) and mt > 0:
                    max_tokens = mt
                elif mt is None:
                    # Effectively unlimited budget
                    max_tokens = 10**9
            except Exception:
                pass

        system_tokens = count_tokens(system_prompt)
        scenario_tokens = count_tokens(scenario)
        prefix_tokens = count_tokens(prefix)
        memory_tokens = sum(m.get("token_count", 0) for m in memories)

        overhead = system_tokens + scenario_tokens + prefix_tokens + memory_tokens + 50
        available_for_rolling = max(0, max_tokens - overhead)

        rolling_memory = []
        total = 0
        for msg in reversed(conversation_history):
            tokens = count_tokens(msg.get("content", ""))
            if total + tokens > available_for_rolling:
                break
            rolling_memory.insert(0, msg)
            total += tokens

        self.trimmed_history = rolling_memory
        self.last_token_stats = {
            "max_tokens": max_tokens,
            "system_tokens": system_tokens,
            "scenario_tokens": scenario_tokens,
            "prefix_tokens": prefix_tokens,
            "memory_tokens": memory_tokens,
            "available_for_rolling": available_for_rolling,
            "rolling_used_tokens": total,
        }

        memory_snippets = "\n\n".join(
            m.get("prompt_text", "").strip() for m in memories if m.get("prompt_text")
        )

        return (
            f"{system_prompt}\n\n"
            f"{scenario.strip()}\n\n"
            f"{prefix.strip()}\n\n"
            f"{memory_snippets.strip()}\n\n"
            f"User: {user_message.strip()}"
        )

    def build_chat_messages(self, conversation_history, scenario, prefix, memories,
                            llm_character_config, user_character_config):
        system_content = self._build_system_message(
            scenario, prefix, memories, llm_character_config, user_character_config
        )

        # Source token budget from Advanced Settings
        max_budget = self.DEFAULT_CONTEXT_TOKEN_BUDGET
        settings_frame = self.controller.frames.get("AdvancedSettings")
        if settings_frame and hasattr(settings_frame, "get_max_tokens"):
            try:
                mt = settings_frame.get_max_tokens()  # may be None if "No Token Limit" is enabled
                if isinstance(mt, int) and mt > 0:
                    max_budget = mt
                elif mt is None:
                    # Treat as effectively unlimited for rolling history
                    max_budget = 10**9
            except Exception:
                pass

        overhead_tokens = self._calculate_overhead_tokens(system_content)
        available_tokens = max(max_budget - overhead_tokens, 0)

        trimmed_history = []
        used_tokens = 0
        for entry in reversed(conversation_history):
            content = entry.get("content", "") or ""
            tokens = count_tokens(content)
            if trimmed_history:
                if used_tokens + tokens > available_tokens:
                    break
            trimmed_history.insert(0, entry)
            used_tokens += tokens

        self.trimmed_history = trimmed_history
        messages = [{"role": "system", "content": system_content}]
        for entry in trimmed_history:
            role = entry.get("role")
            content = entry.get("content")
            if role and content:
                messages.append({"role": role, "content": content})

        return messages, trimmed_history