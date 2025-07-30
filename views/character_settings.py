"""
character_settings.py

Provides a UI panel for editing individual character configurations,
including scenario, prefix instructions, and display color. These values
are stored in `character_config.json` files in the `Character/<name>` folder.

Allows loading/saving of scenarios and prefix instructions from/to separate
text files for easier reuse and editing.
"""
import os
import json
from tkinter import filedialog, messagebox
import customtkinter as ctk
from utils.token_utils import count_tokens
CHARACTER_DIR = "Character"

class CharacterSettings(ctk.CTkFrame):
    def __init__(self, parent, controller):
        """
        Initializes the CharacterSettings frame.

        Builds UI for selecting a character, editing its scenario/prefix,
        and updating display color. Populates dropdown from folders in Character/.

        Args:
            parent: Tkinter parent widget.
            controller: Reference to main app controller (RoleplayApp).
        """
        super().__init__(parent)
        self.controller = controller

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self)
        outer.grid(row=0, column=0, sticky="nsew")

        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(outer)
        inner.grid(row=0, column=0)

        self.character_folder_map = {}
        self.selected_character = ctk.StringVar()
        self.selected_character.trace("w", self.load_character)

        ctk.CTkLabel(inner, text="Select Character:", font=self.get_ui_font()).pack(pady=(10, 0))

        character_display_names = []
        for folder_name in os.listdir(CHARACTER_DIR):
            folder_path = os.path.join(CHARACTER_DIR, folder_name)
            config_path = os.path.join(folder_path, "character_config.json")
            if os.path.isdir(folder_path) and os.path.exists(config_path):
                character_display_names.append(folder_name)
                self.character_folder_map[folder_name] = folder_name

        self.character_dropdown = ctk.CTkOptionMenu(inner, variable=self.selected_character, font=self.get_ui_font())
        self.character_dropdown.pack(pady=(0, 10))

        # Set the list of values explicitly once
        self.character_dropdown.configure(values=character_display_names)

        ctk.CTkLabel(inner, text="Scenario:", font=self.get_ui_font()).pack()
        self.scenario_box = ctk.CTkTextbox(inner, height=100, width=500, font=self.get_ui_font())
        self.scenario_box.pack(pady=(0, 10))

        ctk.CTkButton(inner, text="Load Scenario from File", font=self.get_ui_font(), command=self.load_scenario_from_file).pack(pady=(0, 5))
        ctk.CTkButton(inner, text="Save Scenario to File", font=self.get_ui_font(), command=self.save_scenario_to_file).pack(pady=(0, 10))

        ctk.CTkLabel(inner, text="Prefix Instructions:", font=self.get_ui_font()).pack()
        self.prefix_box = ctk.CTkTextbox(inner, height=180, width=500, font=self.get_ui_font())
        self.prefix_box.pack(pady=(0, 10))

        ctk.CTkButton(inner, text="Load Prefix from File", font=self.get_ui_font(), command=self.load_prefix_from_file).pack(pady=(0, 5))
        ctk.CTkButton(inner, text="Save Prefix to File", font=self.get_ui_font(), command=self.save_prefix_to_file).pack(pady=(0, 10))

        ctk.CTkButton(inner, text="Back to Menu", font=self.get_ui_font(), command=lambda: controller.show_frame("StartMenu")).pack(pady=20)

        if character_display_names:
            self.selected_character.set(character_display_names[0])
            self.load_character()

    def get_ui_font(self):
        """
        Returns the global font size configured in AdvancedSettings.
        Defaults to size 14 if unavailable.
        """
        settings = self.controller.frames.get("AdvancedSettings")
        size = settings.get_text_size() if settings else 14
        return ("Arial", size)

    def apply_theme_colors(self):
        """
        Updates the scenario and prefix textboxes to match global theme colors
        (used when theme is changed in AdvancedSettings).
        """
        entry_bg_color = self.controller.entry_bg_color
        text_color = self.controller.text_color
        accent_color = self.controller.accent_color

        self.scenario_box.configure(fg_color=entry_bg_color, text_color=text_color, border_color=accent_color)
        self.prefix_box.configure(fg_color=entry_bg_color, text_color=text_color, border_color=accent_color)

    def load_character(self, *args):
        """
        Loads the selected character's scenario, prefix, and text color into the UI.
        Triggered when the dropdown changes.
        """
        display_name = self.selected_character.get()
        name = self.character_folder_map.get(display_name, display_name)
        path = os.path.join(CHARACTER_DIR, name, "character_config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.scenario_box.delete("1.0", "end")
                self.prefix_box.delete("1.0", "end")

    def save_character(self):
        """
        Saves the scenario, prefix, and color from the UI into character_config.json.

        Validates that the hex color is correctly formatted. If the currently
        selected character matches, updates ChatView as well.
        """
        display_name = self.selected_character.get()
        name = self.character_folder_map.get(display_name, display_name)
        path = os.path.join(CHARACTER_DIR, name)
        os.makedirs(path, exist_ok=True)
        config_path = os.path.join(path, "character_config.json")
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # Update ChatView if this character is currently active
        current_char = self.controller.selected_character
        if current_char == name:
            chat_view = self.controller.frames.get("ChatView")
            if chat_view:
                chat_view.load_character_assets(force_reload=True)

    def load_scenario_from_file(self):
        """
        Allows the user to load a scenario from a text file located in 
        Character/<name>/Scenarios/. Loads the content into the scenario textbox.
        """
        name = self.selected_character.get()
        scenario_dir = os.path.join(CHARACTER_DIR, self.character_folder_map[name], "Scenarios")
        os.makedirs(scenario_dir, exist_ok=True)
        file_path = filedialog.askopenfilename(initialdir=scenario_dir, title="Select Scenario File", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                text = data.get("content", "")
                self.scenario_box.delete("1.0", "end")
                self.scenario_box.insert("end", text)

    def save_scenario_to_file(self):
        """
        Allows the user to save the current scenario textbox content
        to a .txt file in Character/<name>/Scenarios/.
        """
        name = self.selected_character.get()
        scenario_dir = os.path.join(CHARACTER_DIR, self.character_folder_map[name], "Scenarios")
        os.makedirs(scenario_dir, exist_ok=True)
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialdir=scenario_dir,
            filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            text = self.scenario_box.get("1.0", "end").strip()
            # Save as JSON with token count
            token_count = count_tokens(text)
            json_data = {
                "content": text,
                "token_count": token_count
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2)

    def load_prefix_from_file(self):
        """
        Loads prefix instructions from a text file into the UI.
        Looks in Character/<name>/Prefix/.
        """
        name = self.selected_character.get()
        prefix_dir = os.path.join(CHARACTER_DIR, self.character_folder_map[name], "Prefix")
        os.makedirs(prefix_dir, exist_ok=True)
        file_path = filedialog.askopenfilename(initialdir=prefix_dir, title="Select Prefix File", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                text = data.get("content", "")
                self.prefix_box.delete("1.0", "end")
                self.prefix_box.insert("end", text)

    def save_prefix_to_file(self):
        # Saves the prefix textbox content to a text file in Character/<name>/Prefix/.
        name = self.selected_character.get()
        prefix_dir = os.path.join(CHARACTER_DIR, self.character_folder_map[name], "Prefix")
        os.makedirs(prefix_dir, exist_ok=True)
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialdir=prefix_dir,
            filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            text = self.prefix_box.get("1.0", "end").strip()
            # Save as JSON with token count
            token_count = count_tokens(text)
            json_data = {
                "content": text,
                "token_count": token_count
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2)
