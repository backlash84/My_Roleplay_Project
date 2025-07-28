"""
start_ui.py

Entry point for launching the AI Roleplay Simulator UI.
Initializes the RoleplayApp controller, registers all view frames, loads settings, and starts the main UI loop.
"""

# Core application controller
from core.app_controller import RoleplayApp

# CustomTkinter
import customtkinter as ctk

# UI Views
from views.start_menu import StartMenu
from views.chat_view import ChatView
from views.character_settings import CharacterSettings
from views.advanced_settings import AdvancedSettings

ctk.set_appearance_mode("dark")

if __name__ == "__main__":
    # Initialize main application controller
    app = RoleplayApp()

    # Register each view with the controller and attach it to the container
    for View in (StartMenu, ChatView, CharacterSettings, AdvancedSettings):
        frame = View(parent=app.container, controller=app)
        app.register_view(View.__name__, frame)

    # Load saved settings from config file and apply them to the UI
    app.load_and_apply_settings()

    # Show the Start Menu as the first visible frame
    app.show_frame("StartMenu")

    # Start the event loop
    app.mainloop()
