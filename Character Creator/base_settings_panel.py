import customtkinter as ctk
import json
import os
from tkinter import messagebox
from tkinter import filedialog


class BaseSettingsPanel(ctk.CTkFrame):
    def __init__(self, parent, config_data, config_path):
        super().__init__(parent)
        self.config_path = config_path

        self.entries = {}  # Store input fields for easy access later

        fields = [
            # Core identity
            ("Name", "name"),
            ("Sex", "sex"),
            ("Race", "race"),
            ("Gender Identity", "gender"),
            ("Pronouns", "pronouns"),
            ("Sexual Orientation", "orientation"),
            ("Age", "age"),
            ("Birthday", "birthday"),

            # Personality and style
            ("Personality", "personality"),
            ("Speech Style", "speech_style"),
            ("Accent", "accent"),
            ("Vocal Tone", "vocal_tone"),

            # Appearance
            ("Height", "height"),
            ("Weight", "weight"),
            ("Build", "build"),
            ("Eyes", "eyes"),
            ("Hair", "hair"),
            ("Skin Tone", "skin_tone"),
            ("Distinctive Features", "appearance_notes"),

            # Meta
            ("Text Colour", "text_color"),
            ("Source", "source_type"),
            ("Author", "author"),
            ("Other", "other"),
            ("Notes", "notes")
        ]

        # Enable vertical stretching
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Scrollable Container
        scroll_frame = ctk.CTkScrollableFrame(self, width=600)
        scroll_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=(10, 0))
        scroll_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(scroll_frame, text="Base Settings", font=("Arial", 20)).grid(row=0, column=0, columnspan=2, pady=20)

        # Input Rows (inside scroll frame)
        for idx, (label_text, field_key) in enumerate(fields, start=1):
            ctk.CTkLabel(scroll_frame, text=label_text + ":", anchor="e", width=140).grid(row=idx, column=0, padx=10, pady=5, sticky="e")
            entry = ctk.CTkEntry(scroll_frame, width=400)
            entry.insert(0, config_data.get(field_key, ""))
            entry.grid(row=idx, column=1, padx=10, pady=5, sticky="w")
            self.entries[field_key] = entry

        # Visibility dropdown (still in scroll frame)
        visibility_options = ["shared", "private", "system_only"]
        ctk.CTkLabel(scroll_frame, text="Visibility:", anchor="e", width=140).grid(row=idx + 1, column=0, padx=10, pady=5, sticky="e")
        self.visibility_dropdown = ctk.CTkOptionMenu(scroll_frame, values=visibility_options)
        self.visibility_dropdown.set(config_data.get("visibility", "shared"))
        self.visibility_dropdown.grid(row=idx + 1, column=1, padx=10, pady=5, sticky="w")
        # Save/Load button row
        button_row = ctk.CTkFrame(self)
        button_row.grid(row=len(fields) + 2, column=0, columnspan=2, pady=20)

        ctk.CTkButton(button_row, text="Save", width=100, command=self.save_config).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Load", width=100, command=self.load_config).pack(side="left", padx=10)

    def save_config(self):
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        data["visibility"] = self.visibility_dropdown.get()

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", "Character configuration saved.")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Error saving config:\n{e}")

    def load_config(self):
        folder_path = filedialog.askdirectory(
            title="Select Character Folder",
            initialdir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Character"))
        )

        if not folder_path:
            return  # User cancelled

        file_path = os.path.join(folder_path, "character_config.json")

        if not os.path.exists(file_path):
            messagebox.showerror("Load Failed", "That folder does not contain a character_config.json.")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Failed", f"Error loading config:\n{e}")
            return

        # Update UI
        for key, entry in self.entries.items():
            entry.delete(0, "end")
            entry.insert(0, config_data.get(key, ""))

        self.visibility_dropdown.set(config_data.get("visibility", "shared"))

        # Update path for future saves
        self.config_path = file_path