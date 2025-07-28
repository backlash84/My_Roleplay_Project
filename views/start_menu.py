import os
import json
from tkinter import filedialog
import customtkinter as ctk
CHARACTER_DIR = "Character"

class StartMenu(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.controller.selected_character = None  # store active character name

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self)
        outer.grid(row=0, column=0, sticky="nsew")

        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(outer)
        inner.grid(row=0, column=0)

        font = self.get_ui_font()

        ctk.CTkLabel(inner, text="AI Roleplay Simulator", font=("Arial", self.get_ui_font()[1] + 10)).pack(pady=20)
        ctk.CTkLabel(inner, text="Selected Character:", font=self.get_ui_font()).pack(pady=(0, 5))

        self.character_names = [
            d for d in os.listdir(CHARACTER_DIR)
            if os.path.isdir(os.path.join(CHARACTER_DIR, d))
        ]
        self.character_var = ctk.StringVar()
        self.character_dropdown = ctk.CTkOptionMenu(
            inner,
            variable=self.character_var,
            values=self.character_names,
        )
        self.character_dropdown.pack(pady=(0, 15))

        if self.character_names:
            self.character_var.set(self.character_names[0])
            self.controller.selected_character = self.character_names[0]

        # Sync character selection to controller
        self.character_var.trace_add("write", lambda *args: setattr(self.controller, "selected_character", self.character_var.get()))

        ctk.CTkButton(inner, text="Start Chat", width=200, font=self.get_ui_font(),
                      command=self.start_fresh_chat).pack(pady=10)

        ctk.CTkButton(inner, text="Load Previous Session", width=200, font=self.get_ui_font(),
                      command=self.load_session_from_start).pack(pady=10)

        ctk.CTkButton(inner, text="Character Settings", width=200, font=self.get_ui_font(),
                      command=lambda: controller.show_frame("CharacterSettings")).pack(pady=10)

        ctk.CTkButton(inner, text="Advanced Settings", width=200, font=self.get_ui_font(),
                      command=lambda: controller.show_frame("AdvancedSettings")).pack(pady=10)

        # Fix dropdown color on first load
        self.apply_theme_colors()

    def get_ui_font(self):
        settings = self.controller.frames.get("AdvancedSettings")
        size = settings.get_text_size() if settings else 14
        return ("Arial", size)

    def apply_theme_colors(self):
        self.character_dropdown.configure(
            fg_color=self.controller.accent_color,
            button_color=self.controller.accent_color,
            text_color=self.controller.text_color,
            text_color_disabled=self.controller.text_color
        )

    def start_fresh_chat(self):
        character_name = self.character_var.get()
        self.controller.start_chat(character_name)

    def load_session_from_start(self):
        from utils.session_utils import load_session

        chat_view = self.controller.frames["ChatView"]
        load_session(chat_view)
        self.controller.show_frame("ChatView")