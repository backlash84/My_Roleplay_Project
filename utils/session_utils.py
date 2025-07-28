"""
session_utils.py

Handles saving and loading of user chat sessions, including character selection,
scenario, prefix instructions, and conversation history.

Ensures session persistence and restoration, used by both ChatView and StartMenu
to resume past interactions.
"""
import os
import json
from tkinter import filedialog

def save_session(file_path: str, session_data: dict):
    """
    Saves session data (chat history, prefix, scenario, etc.) to a JSON file.

    Args:
        file_path (str): Destination path for the session file.
        session_data (dict): Dictionary of session data to save.
    """
    # Ensure the Sessions directory exists
    os.makedirs("Sessions", exist_ok=True)

    if not file_path:
        return

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)

def load_session(chat_view, file_path=None):
    """
    Loads a saved chat session into the given ChatView instance.

    If no file path is provided, prompts the user to select a session file.

    Args:
        chat_view (ChatView): The chat view instance to populate with session data.
        file_path (str, optional): Optional path to a saved session JSON file.
    """
    session_dir = "Sessions"
    os.makedirs(session_dir, exist_ok=True)

    if not file_path:
        # Prompt user to choose a session file
        file_path = filedialog.askopenfilename(
            initialdir=session_dir,
            filetypes=[("JSON Files", "*.json")],
            title="Load Previous Session"
        )
        if not file_path:
            return 
    # Load session data from disk
    with open(file_path, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    char_name = session_data.get("character")
    prefix = session_data.get("prefix", "")
    scenario = session_data.get("scenario", "")
    chat_history = session_data.get("conversation_history", [])  # renamed for consistency

    # Restore character and session context
    chat_view.controller.selected_character = char_name
    chat_view.prefix = prefix
    chat_view.scenario = scenario
    chat_view.conversation_history = chat_history
    chat_view.chat_initialized = False

    # Reload FAISS index and character config from disk
    chat_view.load_character_assets(force_reload=True)  # Load memory index + character config

    # Re-render chat view from restored history
    chat_view.render_conversation_to_display()  # Cleanly rebuild UI from history
    chat_view.entry.delete("1.0", "end")  # Clear input
