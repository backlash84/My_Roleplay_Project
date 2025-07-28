# character_creator.py

import customtkinter as ctk
import os
from tkinter import filedialog
from new_character_view import NewCharacterScreen
from character_editor_view import CharacterEditorScreen
from memory_maker_panel import MemoryMakerPanel
from tkinter import messagebox

class CharacterCreatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Character Creator")
        self.geometry("1000x750")

        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True)
        self.show_main_menu()

    def show_main_menu(self):
        # Clear the frame
        for widget in self.container.winfo_children():
            widget.destroy()

        # Title label
        title = ctk.CTkLabel(self.container, text="Character Creator", font=("Arial", 28))
        title.pack(pady=30)

        # Buttons
        ctk.CTkButton(self.container, text="New Character", width=200, command=self.start_new_character).pack(pady=10)
        ctk.CTkButton(self.container, text="Load Character", width=200, command=self.load_character).pack(pady=10)
        ctk.CTkButton(self.container, text="Settings", width=200, command=self.open_settings).pack(pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_new_character(self):
        self.show_new_character_screen()

    def load_character(self):
        character_dir = filedialog.askdirectory(
            title="Select Character Folder",
            initialdir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Character"))
        )

        if not character_dir:
            return  # User cancelled

        config_path = os.path.join(character_dir, "character_config.json")
        if not os.path.exists(config_path):
            messagebox.showerror(
                "Invalid Selection",
                "Selected folder does not contain a character_config.json."
            )
            return

        character_name = os.path.basename(character_dir)
        self.show_editor_screen(character_name, character_dir)

    def open_settings(self):
        print("Settings not implemented yet.")

    def show_new_character_screen(self):
        # Clear and swap to NewCharacterScreen
        for widget in self.container.winfo_children():
            widget.destroy()
        screen = NewCharacterScreen(self.container, self)
        screen.pack(fill="both", expand=True)

    def show_editor_screen(self, character_name, character_path):
        for widget in self.container.winfo_children():
            widget.destroy()
        screen = CharacterEditorScreen(self.container, self, character_name, character_path)
        screen.pack(fill="both", expand=True)

    def on_close(self):
        for widget in self.container.winfo_children():
            if hasattr(widget, "current_panel"):
                if isinstance(widget.current_panel, MemoryMakerPanel):
                    if widget.current_panel.has_unsaved_changes():
                        result = messagebox.askyesno("Unsaved Changes", "You have unsaved memory.\nSave before quitting?")
                        if result:
                            widget.current_panel.save_current_memory()
                    break
        self.destroy()

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")  # optional
    app = CharacterCreatorApp()
    app.mainloop()

