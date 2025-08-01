import customtkinter as ctk
import os
import json
from tkinter import messagebox
from character_editor_view import CharacterEditorScreen

# Point to the shared 'Character' folder (same as main app)
BASE_CHARACTER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Character"))
TEMPLATE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "Templates", "character_config_template.json"))

class NewCharacterScreen(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        ctk.CTkLabel(self, text="New Character Setup", font=("Arial", 22)).pack(pady=20)

        # Name Entry
        ctk.CTkLabel(self, text="Character Name:", font=("Arial", 14)).pack()
        self.name_entry = ctk.CTkEntry(self, width=300)
        self.name_entry.pack(pady=10)

        # Button Row
        button_row = ctk.CTkFrame(self)
        button_row.pack(pady=20)

        ctk.CTkButton(button_row, text="Start", width=120, command=self.create_character).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Back", width=120, command=self.controller.show_main_menu).pack(side="left", padx=10)

    def create_character(self):
        name = self.name_entry.get().strip()

        if not name:
            messagebox.showerror("Missing Name", "Name required before character creation can begin.")
            return

        character_dir = os.path.join(BASE_CHARACTER_DIR, name)

        # Check for existing character
        if os.path.exists(character_dir):
            confirm = messagebox.askyesno(
                "Overwrite Existing Character?",
                f"A character named '{name}' already exists.\n\nOverwrite this character?"
            )
            if not confirm:
                return

        try:
            os.makedirs(character_dir, exist_ok=True)

            # Subfolders
            for subfolder in ["Personal_Memories", "Prefix", "Scenarios", "Sessions"]:
                os.makedirs(os.path.join(character_dir, subfolder), exist_ok=True)

            # --- Create Memory_Templates folder and copy default template ---
            template_subdir = os.path.join(character_dir, "Memory_Templates")
            os.makedirs(template_subdir, exist_ok=True)

            default_template_name = "Test Name.json"
            default_template_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "Templates", "Memory Templates", default_template_name))
            default_template_dest = os.path.join(template_subdir, default_template_name)

            if os.path.exists(default_template_src):
                try:
                    with open(default_template_src, "r", encoding="utf-8") as f:
                        template_data = json.load(f)
                    with open(default_template_dest, "w", encoding="utf-8") as f:
                        json.dump(template_data, f, indent=2)
                    print(f"[INIT] Default memory template copied to: {default_template_dest}")
                except Exception as e:
                    print(f"[ERROR] Failed to copy default template: {e}")
            else:
                print(f"[WARN] Default template not found at: {default_template_src}")

            # Copy template config file
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                template_data = json.load(f)

            config_path = os.path.join(character_dir, "character_config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)

            print(f"Character '{name}' created at: {character_dir}")
            self.controller.show_editor_screen(name, character_dir)
            # TODO: Load config into editor screen next
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create character:\n{e}")

