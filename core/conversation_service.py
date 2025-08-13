"""
conversation_service.py (modified version)

Contains the ConversationService class, which encapsulates the logic for
building prompts, payloads, and conversation history used by the LLM backend.
This version introduces a dynamic, token-budget aware rolling memory system...
"""
import os
from utils.api_utils import call_llm_api
from utils.token_utils import count_tokens
from utils.text_utils import extract_questions, jaccard_like

# ASCII-only helpers for the summarizer
SUMMARIZER_SYSTEM = (
    "You condense roleplay context so an assistant can answer the latest user message in-character."
)

def build_summarizer_user_prompt(raw_context, prefix, last_user):
    return (
        "Goal: Produce a concise context to help the assistant answer the user's latest message.\n\n"
        "Keep only:\n"
        "- Facts from memories relevant to the latest message\n"
        "- Events from history needed to understand the latest message\n"
        "- The explicit question(s) in the user's message (quote verbatim)\n\n"
        "Hard limits:\n"
        "- <= 25% of RAW_CONTEXT length\n"
        "- No long verbatim copying; rephrase tightly\n"
        "- Neutral, factual tone; no extra narration\n\n"
        "[Prefix rules]\n"
        + prefix.strip() + "\n\n"
        "[Latest user message]\n"
        + last_user.strip() + "\n\n"
        "[RAW_CONTEXT]\n"
        + raw_context
    )

class ConversationService:
    """Service layer for building prompts and payloads for the LLM."""
    DEFAULT_CONTEXT_TOKEN_BUDGET = 16000

    def __init__(self, controller):
        self.controller = controller
        self.loaded_scenario_data = {}
        self.loaded_prefix_data = {}
        self.trimmed_history = []

    def _build_system_message(self, scenario, prefix, memories, llm_character_config, user_character_config) -> str:
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
        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        return call_llm_api(url, payload, debug_mode, conversation_history, prompt)

    def build_prompt(self, user_message, memories, scenario, prefix, conversation_history, llm_character_config=None, user_character_config=None) -> str:
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

        max_tokens = self.DEFAULT_CONTEXT_TOKEN_BUDGET
        settings_frame = self.controller.frames.get("AdvancedSettings")
        if settings_frame and hasattr(settings_frame, "get_max_tokens"):
            try:
                mt = settings_frame.get_max_tokens()
                if isinstance(mt, int) and mt > 0:
                    max_tokens = mt
                elif mt is None:
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

    def build_chat_messages(self, conversation_history, scenario, prefix, memories, llm_character_config, user_character_config): 
        system_content = self._build_system_message(scenario, prefix, memories, llm_character_config, user_character_config)
        max_budget = self.DEFAULT_CONTEXT_TOKEN_BUDGET
        settings_frame = self.controller.frames.get("AdvancedSettings")
        if settings_frame and hasattr(settings_frame, "get_max_tokens"):
            try:
                mt = settings_frame.get_max_tokens()
                if isinstance(mt, int) and mt > 0:
                    max_budget = mt
                elif mt is None:
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

    def summarize_text(self, raw_text, settings_data, user_message, prefix, ratio_default=0.25):
        # Empty in, empty out
        if not isinstance(raw_text, str) or not raw_text.strip():
            return ""

        # Ratio + token targets
        try:
            ratio = float(settings_data.get("summary_ratio", ratio_default))
            if ratio <= 0.0 or ratio > 1.0:
                ratio = ratio_default
        except Exception:
            ratio = ratio_default

        raw_tokens = count_tokens(raw_text)
        target_tokens = max(64, int(raw_tokens * ratio))
        max_summary_tokens = settings_data.get(
            "summary_max_tokens",
            max(256, min(1024, target_tokens * 2))
        )

        # Build messages
        system_msg = SUMMARIZER_SYSTEM
        user_prompt = build_summarizer_user_prompt(
            raw_context=raw_text,
            prefix=prefix,
            last_user=user_message
        )

        payload = {
            "model": settings_data.get("model"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": max_summary_tokens,
        }

        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        summary = call_llm_api(url, payload, show_debug=False)
        if not isinstance(summary, str) or not summary.strip():
            # API error or empty string -> fallback
            return raw_text

        summary_text = summary.strip()

        # Very basic anti-parroting: if it barely compressed, try once more
        if len(summary_text) >= int(0.9 * len(raw_text)):
            tightened = user_prompt + (
                "\n\nHARD LIMITS:\n"
                "- Compress to <= 20% of RAW_CONTEXT.\n"
                "- Do not copy any phrase longer than 12 words verbatim."
            )
            payload_retry = dict(payload)
            payload_retry["messages"] = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": tightened},
            ]
            payload_retry["max_tokens"] = min(max_summary_tokens, 512)
            summary2 = call_llm_api(url, payload_retry, show_debug=False)
            if isinstance(summary2, str) and summary2.strip():
                summary_text = summary2.strip()

        return summary_text

    def compose_final_messages(
        self,
        summary_text: str,
        scenario: str,
        prefix: str,
        llm_character_config: dict,
        user_character_config: dict,
        user_message: str,
    ) -> list:
        """
        Build the final OpenAI-style messages array that will be sent to the model.
        Uses the summary as canonical context, not the full memories/history.
        """
        llm_name = (llm_character_config or {}).get("name", "Unknown Character")
        llm_info = (llm_character_config or {}).get("character_information", "").strip()
        user_name = (user_character_config or {}).get("name", "Unknown Player")
        user_info = (user_character_config or {}).get("character_information", "").strip()

        system_lines = []
        system_lines.append("You are playing as this character:")
        system_lines.append(f"Name: {llm_name}")
        system_lines.append("Character Information:")
        system_lines.append(llm_info)
        system_lines.append("")
        system_lines.append("The user is playing as this character:")
        system_lines.append(f"Name: {user_name}")
        system_lines.append("Character Information:")
        system_lines.append(user_info)
        system_lines.append("")
        system_lines.append(scenario.strip())
        system_lines.append("")
        system_lines.append(prefix.strip())
        system_lines.append("")
        system_lines.append("RULE: Use the Summary of Context below as the canonical state. Do not ignore it.")
        system_lines.append("=== Summary of Context ===")
        system_lines.append(summary_text.strip() if summary_text else "(no summary)")
        system_msg = "\n".join(system_lines).strip()

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_message.strip()},
        ]

    def build_raw_prompt_input(self, memories: list, trimmed_history: list) -> str:
        """
        Minimal raw prompt: only pulled memories (full text) and rolling history.
        No scenario/prefix/configs/timestamps.
        """
        mem_texts = []
        for m in memories or []:
            t = (m.get("prompt_text") or "").strip()
            if t:
                mem_texts.append(t)

        hist_lines = []
        for e in trimmed_history or []:
            role = e.get("role", "?")
            content = (e.get("content") or "").strip()
            hist_lines.append(f"[role={role}] {content}")

        parts = []
        parts.append("--- Retrieved Memories (full) ---")
        parts.append("\n\n".join(mem_texts) if mem_texts else "(none)")
        parts.append("")
        parts.append("--- Rolling History (oldest -> newest) ---")
        parts.append("\n".join(hist_lines) if hist_lines else "(none)")
        return "\n".join(parts).strip()


    def summarize_text(self, raw_text: str, settings_data: dict, user_message: str, prefix: str, ratio_default: float = 0.25) -> str:
        """
        Summarize raw_text to ~ratio_default size, aimed at helping respond to user_message,
        while keeping the prefix rules in mind. Falls back to raw_text on failure.
        """
        if not isinstance(raw_text, str) or not raw_text.strip():
            return ""

        # Target size hint (optional; the prompt enforces 25% anyway)
        raw_tokens = count_tokens(raw_text)
        target_tokens = max(64, int(raw_tokens * ratio_default))
        max_summary_tokens = settings_data.get("summary_max_tokens", max(256, min(1024, target_tokens * 2)))

        user_prompt = build_summarizer_user_prompt(
            raw_context=raw_text,
            prefix=prefix or "",
            last_user=user_message or ""
        )

        payload = {
            "model": settings_data.get("model"),
            "messages": [
                {"role": "system", "content": SUMMARIZER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": max_summary_tokens,
        }

        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        summary = call_llm_api(url, payload, show_debug=False)
        if not isinstance(summary, str) or not summary.strip():
            return raw_text
        return summary.strip()