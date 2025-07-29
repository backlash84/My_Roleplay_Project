import os
import json
from tkinter import filedialog

def save_session(file_path: str, session_data: dict):
    """
    Saves session data (chat history, prefix, scenario, etc.) to a JSON file.
    Used only for manual saves (optional now due to new session system).
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if not file_path:
        return

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

def load_session(chat_view, file_path=None):
    """
    Loads a saved chat session into the ChatView.

    If no file path is provided, prompts the user to select a session_info.json file
    from a character's Sessions folder.

    Args:
        chat_view (ChatView): The chat view instance to populate.
        file_path (str, optional): Optional direct path to a session_info.json file.
    """
    base_path = "Character"
    if not file_path:
        file_path = filedialog.askopenfilename(
            initialdir=base_path,
            filetypes=[("JSON Files", "*.json")],
            title="Load Previous Session"
        )
        if not file_path:
            return

    with open(file_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    chat_view.controller.active_session_data = session_data

    # Load history file if it exists
    session_dir = os.path.dirname(file_path)
    history_path = os.path.join(session_dir, "chat_log.json")

    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            chat_view.conversation_history = json.load(f)
    else:
        chat_view.conversation_history = []

    chat_view.chat_initialized = False
    chat_view.load_session_assets(force_reload=True)
    chat_view.render_conversation_to_display()
    chat_view.entry.delete("1.0", "end")