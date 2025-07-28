import datetime
import json

# For chat display
def generate_basic_debug_report(payload: dict, memory_debug_lines: list[str], selected_memories: list[str]) -> str:
    lines = ["=== Memory Debug ==="]

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
    prefix_ui: str = ""
) -> str:
    lines = [f"=== Advanced Debug Report ==="]
    lines.append(f"Generated at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # === Scenario / Prefix ===
    lines.append("--- Scenario in Settings Menu ---")
    lines.append(scenario_ui.strip() or "(none)")
    lines.append("\n--- Scenario Sent to AI ---")
    lines.append(scenario_sent.strip() or "(none)")

    lines.append("\n--- Prefix in Settings Menu ---")
    lines.append(prefix_ui.strip() or "(none)")
    lines.append("\n--- Prefix Sent to AI ---")
    lines.append(prefix_sent.strip() or "(none)")

    # === LLM Settings: UI and Used ===
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

        if api_val is None or str(api_val).lower() == "none":
            override_note = ""
        elif str(ui_val) != str(api_val):
            override_note = f" (used: {api_val})"
        else:
            override_note = ""
        lines.append(f"{key.replace('_', ' ').title()}: {ui_val}{override_note}")

    # === Memory Debug ===
    lines.append("\n--- Raw FAISS Distances and Boosted Scores ---")
    lines.extend(memory_debug_lines or ["(no memory debug data provided)"])
    lines.append(f"\nReturned {len(selected_memories)} memory chunk(s) after filtering.")
    if selected_memories:
        lines.append("--- Selected Memory Content ---")
        for i, mem in enumerate(selected_memories, 1):
            lines.append(f"Memory {i}: {mem.strip().replace('[Memory] ', '', 1)}\n")

    # === Rolling Memory ===
    lines.append("\n=== Rolling Memory ===")
    for i, msg in enumerate(conversation_history, 1):
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        lines.append(f"{i}. [{role}] {content}")
    lines.append("=== End Rolling Memory ===")

    # === Final API Payload ===
    lines.append("\n--- Final API Payload ---")
    try:
        lines.append(json.dumps(prompt_payload, indent=2))
    except Exception as e:
        lines.append(f"[Error serializing payload: {e}]")

    lines.append("=== End Debug Report ===\n")
    return "\n".join(lines)