"""
conversation_service.py (modified version)

Contains the ConversationService class, which encapsulates the logic for
building prompts, payloads, and conversation history used by the LLM backend.
This version introduces a dynamic, token-budget aware rolling memory system...
"""
import re
import os
import json
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
            f"You are to follow these instructions:\n"
            f"{prefix.strip()}"
            f"You are playing as this character:\n"
            f"Name: {llm_name}\n"
            f"Character Information:\n{llm_info}\n\n"
            f"The user is playing as this character:\n"
            f"Name: {user_name}\n"
            f"Character Information:\n{user_info}\n\n"
            f"This is the scenario you find yourself in:\n"
            f"{scenario.strip()}\n\n"
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

    def build_prompt(
        self,
        user_message,
        memories,
        scenario,
        prefix,
        conversation_history,
        llm_character_config=None,
        user_character_config=None
    ) -> str:
        """
        Builds a single-string prompt for legacy callers.
        Includes:
          - Character system info (brief)
          - Scenario + Prefix
          - Combined context:
              * Memory monologue (self.last_memory_summary) if set
              * Rolling history summary (self.last_rolling_summary) if set
          - Latest user message

        Notes:
          - Set self.last_memory_summary in chat_view right after you get mems_summary_text.
          - (Optional) Set self.last_rolling_summary if you also summarize rolling history.
          - We still compute token stats and trimmed history for debug.
        """
        # Make latest retrieved memories available to other helpers
        self.controller.last_retrieved_memories = memories

        # Character/user configs
        config = llm_character_config or {}
        llm_name = (config.get("name") or "Unnamed Character").strip()
        llm_info = (config.get("character_information") or "").strip()
        user_config = user_character_config or {}
        user_name = (user_config.get("name") or "Player").strip()
        user_info = (user_config.get("character_information") or "").strip()

        # System prompt (compact; detailed versions live elsewhere)
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

        # Token budget
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

        # Compute simple token stats (approximate)
        system_tokens = count_tokens(system_prompt)
        scenario_tokens = count_tokens(scenario or "")
        prefix_tokens = count_tokens(prefix or "")
        memory_tokens = sum(m.get("token_count", 0) for m in (memories or []))
        overhead = system_tokens + scenario_tokens + prefix_tokens + memory_tokens + 50

        # Build trimmed rolling history snapshot (for debug; not injected verbatim here)
        available_for_rolling = max(0, max_tokens - overhead)
        rolling_memory = []
        total = 0
        for msg in reversed(conversation_history or []):
            tokens = count_tokens(msg.get("content", "") or "")
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

        # Combined context block
        mem_summary = (getattr(self, "last_memory_summary", "") or "").strip()
        roll_summary = (getattr(self, "last_rolling_summary", "") or "").strip()

        combined_lines = []
        combined_lines.append("Combined context to consider:")

        if mem_summary:
            combined_lines.append("<<<MEMORY MONOLOGUE>>>")
            combined_lines.append(mem_summary)
            combined_lines.append("<<<END MEMORY MONOLOGUE>>>")

        if roll_summary:
            combined_lines.append("")
            combined_lines.append("<<<ROLLING HISTORY SUMMARY>>>")
            combined_lines.append(roll_summary)
            combined_lines.append("<<<END ROLLING HISTORY SUMMARY>>>")

        combined_block = "\n".join(combined_lines).strip()

        # Final prompt string (single user message style)
        # This function returns a string; callers that use messages[] should prefer build_chat_messages.
        prompt_parts = [
            system_prompt.strip(),
            (scenario or "").strip(),
            (prefix or "").strip(),
        ]
        if combined_block:
            prompt_parts.append(combined_block)

        prompt_parts.append("Latest user message:")
        prompt_parts.append((user_message or "").strip())

        return "\n\n".join([p for p in prompt_parts if p]).strip()

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

    def build_raw_history_input(self, trimmed_history: list) -> str:
        """
        Minimal raw prompt for summarizing ONLY the rolling history.
        No memories, no scenario/prefix/configs.
        """
        hist_lines = []
        for e in trimmed_history or []:
            role = e.get("role", "?")
            content = (e.get("content") or "").strip()
            hist_lines.append(f"[role={role}] {content}")

        parts = []
        parts.append("--- Rolling History (oldest -> newest) ---")
        parts.append("\n".join(hist_lines) if hist_lines else "(none)")
        return "\n".join(parts).strip()

    # ========== NEW: Memory helpers ==========

    def _extract_perspective(self, mem: dict) -> str:
        """
        Try to read a normalized perspective from the memory object.
        Order of preference:
          1) explicit field (perspective or __perspective__)
          2) [PERSPECTIVE: ...] header inside prompt_text
        Returns one of: 'First Hand', 'Second Hand', 'Lore' (fallback: 'Unknown').
        """
        # explicit field
        for key in ("perspective", "__perspective__", "Perspective", "PERSPECTIVE"):
            val = mem.get(key)
            if isinstance(val, str) and val.strip():
                v = val.strip().lower()
                if "first" in v:
                    return "First Hand"
                if "second" in v:
                    return "Second Hand"
                if "lore" in v:
                    return "Lore"

        # parse from prompt_text header
        pt = (mem.get("prompt_text") or "").strip()
        m = re.search(r"\[PERSPECTIVE:\s*([^\]]+)\]", pt, flags=re.IGNORECASE)
        if m:
            v = m.group(1).strip().lower()
            if "first" in v:
                return "First Hand"
            if "second" in v:
                return "Second Hand"
            if "lore" in v:
                return "Lore"

        return "Unknown"



        """
        Build a RAW blob containing ONLY the retrieved memories, grouped by perspective.
        Also includes any 'prompt_context' if present on each memory.
        """
        buckets = {"First Hand": [], "Second Hand": [], "Lore": [], "Unknown": []}
        for m in memories or []:
            pt = (m.get("prompt_text") or "").strip()
            if not pt:
                continue
            ctx = (m.get("prompt_context") or "").strip()
            perspective = self._extract_perspective(m)
            buckets.setdefault(perspective, [])
            entry_lines = []
            entry_lines.append("=== Memory ===")
            entry_lines.append("As text:")
            entry_lines.append(pt)
            if ctx:
                entry_lines.append("")
                entry_lines.append("What it means (annotated):")
                entry_lines.append(ctx)
            buckets[perspective].append("\n".join(entry_lines).strip())

        parts = []
        parts.append(f"LLM Character: {llm_char_name}")
        parts.append("")
        parts.append("User's latest message (for relevance):")
        parts.append(user_message.strip())
        parts.append("")

        # First Hand
        parts.append("These are events your character personally witnessed:")
        block = "\n\n".join(buckets["First Hand"]) if buckets["First Hand"] else "(none)"
        parts.append(block)
        parts.append("")

        # Second Hand
        parts.append("These are events your character heard about from a third party:")
        block = "\n\n".join(buckets["Second Hand"]) if buckets["Second Hand"] else "(none)"
        parts.append(block)
        parts.append("")

        # Lore
        parts.append("These are facts about the world your character is aware of:")
        block = "\n\n".join(buckets["Lore"]) if buckets["Lore"] else "(none)"
        parts.append(block)

        # Unknown (only if present)
        if buckets["Unknown"]:
            parts.append("")
            parts.append("Uncategorized memories (perspective unclear):")
            parts.append("\n\n".join(buckets["Unknown"]))

        return "\n".join(parts).strip()

    def build_raw_memories_input(self, memories: list, llm_char_name=None, user_message=None) -> str:
        """
        EXACTLY what the LLM should see for the memory-summarization step:
        - Your instruction paragraph (editor wording)
        - Three sections (First Hand, Second Hand, Lore)
        - Each entry: (Memory N) followed by lines of '(Prompt Instructions): <value>'
        - Ends with (END)

        We use the memory's 'template_used' to load:
        Character/<LLM Character>/Memory_Template/<template_used>.json

        From that template we include ONLY fields where:
            usage in {Prompt, Both} AND prompt_instructions is present.

        For each such field, we render:
            (<prompt_instructions>): <value from memory>

        Notes:
        - Values may be strings or lists (joined with ', ').
        - Perspective is inferred via _extract_perspective(...).
        - If a section is empty, we write '(none)'.
        - llm_char_name and user_message are accepted but unused (kept for call-site compatibility).
        """
        buckets = {"First Hand": [], "Second Hand": [], "Lore": []}
        counters = {"First Hand": 0, "Second Hand": 0, "Lore": 0}

        # Pre-load template cache by name to avoid repeated disk IO
        template_cache: dict[str, dict] = {}

        for m in memories or []:
            # Resolve perspective
            p = self._extract_perspective(m)
            if p not in buckets:
                continue

            # Resolve template
            tmpl_name = (m.get("template_used") or "").strip()
            tmpl = None
            if tmpl_name:
                tmpl = template_cache.get(tmpl_name)
                if tmpl is None:
                    tmpl = self._load_template_by_name(tmpl_name)
                    template_cache[tmpl_name] = tmpl

            # Collect label->instructions pairs from template
            pairs: list[tuple[str, str]] = []
            if tmpl:
                pairs = self._collect_prompt_fields(tmpl)

            # Build one memory entry, using ONLY template-defined prompt fields
            entry_lines = []
            counters[p] += 1
            idx = counters[p]
            entry_lines.append(f"(Memory {idx})")

            # Always start with prompt_text
            pt = (m.get("prompt_text") or "").strip()
            if not pt:
                counters[p] -= 1
                continue
            entry_lines.append(pt)

            # Then add all annotated fields from the template
            for label, instr in pairs:
                if label.strip().lower() == "prompt_text":
                    continue

                val = None
                label_clean = label.strip().lower()
                for k, v in m.items():
                    if isinstance(k, str) and k.strip().lower() == label_clean:
                        val = v
                        break

                if val is None:
                    print(f"[DEBUG] Skipped missing field: {label}")
                    continue

                # Format value
                if isinstance(val, (list, tuple)):
                    val_str = ", ".join(str(x).strip() for x in val if str(x).strip())
                else:
                    val_str = str(val).strip()

                if not val_str:
                    continue

                # ? This line is what should show up
                entry_lines.append(f"{instr.strip()}: {val_str}")

                entry_lines.append(f"{instr.strip()}: {val_str}")

            buckets[p].append("\n".join(entry_lines).strip())

        # Build top instructions and the 3 sections
        lines = []
        # EXACT instruction text you provided (ASCII only)
        lines.append(
            "You are functioning as an editor. "
            "Your job is to look at the users message, then at the memories that have been pulled that relate to that message.\n\n"
            "Your job is to determine what information is relevant to what is going on in the story, and copy it verbatim, including the context around the relevant information."
        )
        lines.append("")

        lines.append("These are events your character personally witnessed:")
        lines.append("\n\n".join(buckets["First Hand"]) if buckets["First Hand"] else "(none)")
        lines.append("")

        lines.append("These are events your character heard about from a third party:")
        lines.append("\n\n".join(buckets["Second Hand"]) if buckets["Second Hand"] else "(none)")
        lines.append("")

        lines.append("These are facts about the world your character is aware of:")
        lines.append("\n\n".join(buckets["Lore"]) if buckets["Lore"] else "(none)")
        lines.append("")
        lines.append("(END)")

        return "\n".join(lines).strip()

    def summarize_memories(self, raw_mems_text: str = "", settings_data: dict = None, user_message: str = "", llm_char_name: str = "", **_ignored) -> str:
        """
        Accepts the already-built memory prompt (raw_mems_text), sends it to the LLM,
        saves 'RAG Memory Input.txt' and 'RAG Memory Output.txt', and returns the LLM text.

        We do NOT rebuild the prompt here; we use exactly what the caller provided.
        """
        human_prompt = (raw_mems_text or "").strip()

        # Save EXACT prompt as-is
        try:
            sess = getattr(self.controller, "active_session_data", {}) or {}
            char = sess.get("llm_character") or sess.get("character_name") or "UnknownCharacter"
            session_name = sess.get("session_name") or "UnknownSession"
            session_dir = os.path.join("Character", char, "Sessions", session_name)
            os.makedirs(session_dir, exist_ok=True)
            prompt_path = os.path.join(session_dir, "RAG Memory Input.txt")
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(human_prompt)
            print(f"[Saved] {prompt_path}")
        except Exception as e:
            print(f"[WARN] Could not save RAG Memory Input: {e}")

        # Build payload
        settings_data = settings_data or {}
        payload = {
            "model": settings_data.get("model"),
            "messages": [{"role": "user", "content": human_prompt}],
            "temperature": float(settings_data.get("temperature", 0.2)),
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "max_tokens": int(settings_data.get("summary_max_tokens", 800)),
        }

        # Call LLM
        url = self.controller.frames["AdvancedSettings"].get_llm_url()
        result_text = call_llm_api(url, payload, show_debug=False)
        if not isinstance(result_text, str):
            result_text = ""

        # Save EXACT output as-is
        try:
            out_path = os.path.join(session_dir, "RAG Memory Output.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result_text.strip())
            print(f"[Saved] {out_path}")
        except Exception as e:
            print(f"[WARN] Could not save RAG Memory Output: {e}")

        return result_text.strip()

    # ========= NEW: exact-human-format memory prompt builders =========

    def _load_template_by_name(self, template_name: str) -> dict | None:
        """
        Loads Character/<LLM Character>/Memory_Template/<template_name>.json
        Returns dict or None if not found/invalid.
        """
        try:
            sess = getattr(self.controller, "active_session_data", {}) or {}
            # Prefer explicit character_path if present
            char_path = sess.get("character_path")
            if not char_path:
                # Fallback from llm_character
                char = sess.get("llm_character") or sess.get("character_name") or ""
                if not char:
                    return None
                char_path = os.path.join("Character", char)

            tmpl_path = os.path.join(char_path, "Memory_Template", f"{template_name}.json")
            if not os.path.exists(tmpl_path):
                return None
            with open(tmpl_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("fields"):
                return data
        except Exception as e:
            print(f"[WARN] _load_template_by_name failed for '{template_name}': {e}")
        return None

    def _collect_prompt_fields(self, template_doc: dict) -> list[tuple[str, str]]:
        """
        From a template document, return [(label, prompt_instructions)] for fields
        whose usage is 'Prompt' or 'Both' AND that define prompt_instructions.
        """
        results = []
        try:
            for fld in template_doc.get("fields", []):
                usage = (fld.get("usage") or "").strip().lower()
                if usage not in ("prompt", "both"):
                    continue
                instr = (fld.get("prompt_instructions") or "").strip()
                if not instr:
                    continue
                label = fld.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                results.append((label, instr))
        except Exception as e:
            print(f"[WARN] _collect_prompt_fields: {e}")
        return results