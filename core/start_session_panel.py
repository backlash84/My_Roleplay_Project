import customtkinter as ctk
import os
import json
from tkinter import messagebox

class StartSessionPanel(ctk.CTkFrame):
    def __init__(self, parent, controller, character_base_path="Character"):
        super().__init__(parent)
        self.controller = controller

        self.base_character_path = character_base_path
        self.character_folders = self.get_character_list()

        # Row/Column Config
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        frame = ctk.CTkFrame(self)
        frame.grid(padx=30, pady=30)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Start New Session", font=("Arial", 20)).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Session Name
        ctk.CTkLabel(frame, text="Session Name:").grid(row=1, column=0, sticky="e", padx=10, pady=5)
        self.session_name_entry = ctk.CTkEntry(frame, width=300)
        self.session_name_entry.grid(row=1, column=1, sticky="w", padx=10)

        # LLM Character
        ctk.CTkLabel(frame, text="Character (LLM-controlled):").grid(row=2, column=0, sticky="e", padx=10, pady=5)
        self.character_dropdown = ctk.CTkOptionMenu(frame, values=self.character_folders)
        self.character_dropdown.grid(row=2, column=1, sticky="w", padx=10)

        # User Character
        ctk.CTkLabel(frame, text="User (You):").grid(row=3, column=0, sticky="e", padx=10, pady=5)
        self.user_dropdown = ctk.CTkOptionMenu(frame, values=self.character_folders)
        self.user_dropdown.grid(row=3, column=1, sticky="w", padx=10)

        # Scenario
        ctk.CTkLabel(frame, text="Scenario:").grid(row=4, column=0, sticky="e", padx=10, pady=5)
        self.scenario_dropdown = ctk.CTkOptionMenu(frame, values=[])
        self.scenario_dropdown.grid(row=4, column=1, sticky="w", padx=10)

        # Prefix
        ctk.CTkLabel(frame, text="Prefix:").grid(row=5, column=0, sticky="e", padx=10, pady=5)
        self.prefix_dropdown = ctk.CTkOptionMenu(frame, values=[])
        self.prefix_dropdown.grid(row=5, column=1, sticky="w", padx=10)

        # Hook up scenario/prefix update on character change
        self.character_dropdown.configure(command=self.update_scenario_prefix_lists)

        # Start Button
        ctk.CTkButton(frame, text="Start", command=self.start_session).grid(row=6, column=0, columnspan=2, pady=20)

        # Initialize scenario/prefix lists
        if self.character_folders:
            self.update_scenario_prefix_lists(self.character_folders[0])

    def get_character_list(self):
        if not os.path.exists(self.base_character_path):
            return []
        return [name for name in os.listdir(self.base_character_path)
                if os.path.isdir(os.path.join(self.base_character_path, name))]

    def update_scenario_prefix_lists(self, selected_character):
        char_path = os.path.join(self.base_character_path, selected_character)
        scenario_dir = os.path.join(char_path, "Scenarios")
        prefix_dir = os.path.join(char_path, "Prefix")

        scenario_files = [f for f in os.listdir(scenario_dir) if f.endswith(".txt")] if os.path.exists(scenario_dir) else []
        prefix_files = [f for f in os.listdir(prefix_dir) if f.endswith(".txt")] if os.path.exists(prefix_dir) else []

        self.scenario_dropdown.configure(values=scenario_files)
        self.prefix_dropdown.configure(values=prefix_files)

        if scenario_files:
            self.scenario_dropdown.set(scenario_files[0])
        if prefix_files:
            self.prefix_dropdown.set(prefix_files[0])

    def start_session(self):
        session_name = self.session_name_entry.get().strip()
        character = self.character_dropdown.get()
        user = self.user_dropdown.get()
        scenario = self.scenario_dropdown.get()
        prefix = self.prefix_dropdown.get()

        if not session_name:
            messagebox.showerror("Missing Info", "Please enter a session name.")
            return

        session_data = {
            "session_name": session_name,
            "llm_character": character,
            "user_character": user,
            "scenario_file": scenario,
            "prefix_file": prefix
        }

        self.start_callback(session_data)