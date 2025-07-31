import datetime
import json

# For chat display
def generate_basic_debug_report(
    payload: dict,
    memory_debug_lines: list[str],
    selected_memories: list[str],
    token_stats: dict | None = None,
) -> str:
    """Generate a simplified debug report shown in the chat UI."""

    token_stats = token_stats or {}

    lines = ["=== Memory Debug ==="]
     # --- Token Usage ---
    lines.append("\n--- Token Usage Breakdown ---")
    max_tokens = token_stats.get("max_tokens", payload.get("max_tokens", "(not set)"))
    lines.append(f"Max LLM Tokens: {max_tokens}")
    lines.append(f"System Prompt: {token_stats.get('system_tokens', 0)} tokens")
    lines.append(f"Scenario File: {token_stats.get('scenario_tokens', 0)} tokens")
    lines.append(f"Prefix File: {token_stats.get('prefix_tokens', 0)} tokens")
    lines.append(f"Memory Chunks: {token_stats.get('memory_tokens', 0)} tokens")
    lines.append(
        f"Available for Rolling Memory: {token_stats.get('available_for_rolling', 0)}"
    )
    lines.append(
        f"Used for Rolling Memory: {token_stats.get('rolling_used_tokens', 0)}"
    )

    # Memory parameters
    lines.append(f"Top K (Chunks): {payload.get('top_k', '???')}")
    lines.append(f"Similarity Threshold: {payload.get('similarity_threshold', '???')}\n")

    # LLM settings
    lines.append("--- LLM Settings Used ---")
    lines.append(f"Model: {payload.get('model', '???')}")
    lines.append(f"Temperature: {payload.get('temperature', '???')}")

    max_tokens = payload.get("max_tokens")
    lines.append(f"Max Tokens: {max_tokens if max_tokens is not None else 'No Limit'}")

    lines.append(f"Frequency Penalty: {payload.get('frequency_penalty', '???')}")
    lines.append(f"Presence Penalty: {payload.get('presence_penalty', '???')}\n")

    # Memory scoring
    if memory_debug_lines:
        lines.append("--- Scoring Breakdown ---")
        lines.extend(memory_debug_lines)
        lines.append("")  # Add spacing if present

    lines.append(f"Returned {len(selected_memories)} memory chunk(s) after filtering.")
    lines.append("See console for more details.")
    lines.append("=== End Memory Debug ===\n")

    return "\n".join(lines)

# For console
def generate_advanced_debug_report(
    settings_data: dict,
    scenario_sent: str,
    prefix_sent: str,
    memory_debug_lines: list[str],
    selected_memories: list[str],
    conversation_history: list[dict],
    prompt_payload: dict,
    raw_prompt: str,
    scenario_ui: str = "",
    prefix_ui: str = "",
    llm_character_config: dict = None,
    user_character_config: dict = None,
    max_tokens=None,
    system_tokens=None,
    scenario_tokens=None,
    prefix_tokens=None,
    memory_tokens=None,
    available_for_rolling=None,
    rolling_used_tokens=None
) -> str:
    lines = [f"=== Advanced Debug Report ==="]
    lines.append(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    lines.append("\n--- Token Usage Breakdown ---")
    lines.append(f"Max LLM Tokens: {max_tokens if max_tokens is not None else '(unknown)'}")
    lines.append(f"System Prompt: {system_tokens or 0} tokens")
    lines.append(f"Scenario File: {scenario_tokens or 0} tokens")
    lines.append(f"Prefix File: {prefix_tokens or 0} tokens")
    lines.append(f"Memory Chunks: {memory_tokens or 0} tokens")
    lines.append(f"Available for Rolling Memory: {available_for_rolling or 0}")
    lines.append(f"Used for Rolling Memory: {rolling_used_tokens or 0}")

    # Characters
    lines.append("--- Character Info ---")
    llm_char = settings_data.get("llm_character") or "(not set)"
    user_char = settings_data.get("user_character") or "(not set)"
    lines.append(f"LLM-Controlled Character: {llm_char}")
    if llm_character_config:
        llm_desc = llm_character_config.get("character_information", "").strip()
        if llm_desc:
            lines.append("Character Description:")
            lines.append(llm_desc)
    lines.append("")  # spacing

    lines.append(f"User-Controlled Character: {user_char}")
    if user_character_config:
        user_desc = user_character_config.get("character_information", "").strip()
        if user_desc:
            lines.append("Character Description:")
            lines.append(user_desc)
    lines.append("")  # extra line for clarity

    # Scenario & Prefix
    lines.append("--- Scenario in Settings Menu ---")
    lines.append(scenario_ui.strip() or "(none)")
    lines.append("\n--- Scenario Sent to AI ---")
    lines.append(scenario_sent.strip() or "(none)")

    lines.append("\n--- Prefix in Settings Menu ---")
    lines.append(prefix_ui.strip() or "(none)")
    lines.append("\n--- Prefix Sent to AI ---")
    lines.append(prefix_sent.strip() or "(none)")

    # LLM Settings
    lines.append("\n--- LLM Settings Comparison ---")
    display_keys = [
        "max_tokens", "chat_history_length", "top_k", "similarity_threshold",
        "temperature", "memory_boost", "frequency_penalty", "presence_penalty",
        "auto_scroll", "llm_url", "model", "save_path"
    ]

    for key in display_keys:
        ui_val = settings_data.get(key)
        if key == "max_tokens" and settings_data.get("no_token_limit"):
            ui_val = "None"
        if isinstance(ui_val, bool):
            ui_val = "Yes" if ui_val else "No"

        api_val = prompt_payload.get(key)
        if key == "auto_scroll":
            api_val = "Yes" if settings_data.get("auto_scroll") else "No"
        if key == "model":
            api_val = prompt_payload.get("model")
        if key == "save_path":
            api_val = settings_data.get("save_path", "") or "(none)"

        override_note = ""
        if api_val is not None and str(api_val).lower() != str(ui_val).lower():
            override_note = f" (used: {api_val})"
        lines.append(f"{key.replace('_', ' ').title()}: {ui_val}{override_note}")

    # Memory debug
    lines.append("\n--- Raw FAISS Distances and Boosted Scores ---")
    lines.extend(memory_debug_lines or ["(no memory debug data provided)"])
    lines.append(f"\nReturned {len(selected_memories)} memory chunk(s) after filtering.")
    if selected_memories:
        lines.append("--- Selected Memory IDs ---")
        for i, mem in enumerate(selected_memories, 1):
            mem_str = str(mem).strip().replace("[Memory] ", "", 1)
            lines.append(f"Memory {i}: {mem_str}")

    # Rolling memory
    lines.append("\n=== Rolling Memory ===")
    for i, msg in enumerate(conversation_history, 1):
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        lines.append(f"{i}. [{role}] {content}")
    lines.append("=== End Rolling Memory ===")

    # Final payload
    lines.append("\n--- Final API Payload ---")
    try:
        lines.append(json.dumps(prompt_payload, indent=2))
    except Exception as e:
        lines.append(f"[Error serializing payload: {e}]")

    lines.append("=== End Debug Report ===\n")
    return "\n".join(lines)