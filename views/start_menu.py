import os
import json
import customtkinter as ctk
from tkinter import messagebox, filedialog
from utils.session_utils import load_session

CHARACTER_DIR = "Character"

class StartMenu(ctk.CTkFrame):
    def __init__(self, parent, controller):
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

        font = self.get_ui_font()

        ctk.CTkLabel(inner, text="AI Roleplay Simulator", font=("Arial", font[1] + 10)).pack(pady=20)

        ctk.CTkButton(inner, text="Start Chat", width=200, font=font,
                      command=self.launch_start_session_panel).pack(pady=10)

        ctk.CTkButton(inner, text="Load Previous Session", width=200, font=font,
                      command=self.load_session_from_start).pack(pady=10)

        ctk.CTkButton(inner, text="Character Settings", width=200, font=font,
                      command=lambda: controller.show_frame("CharacterSettings")).pack(pady=10)

        ctk.CTkButton(inner, text="Advanced Settings", width=200, font=font,
                      command=lambda: controller.show_frame("AdvancedSettings")).pack(pady=10)

    def get_ui_font(self):
        settings = self.controller.frames.get("AdvancedSettings")
        size = settings.get_text_size() if settings else 14
        return ("Arial", size)

    def launch_start_session_panel(self):
        self.controller.show_frame("StartSessionPanel")  # Make sure it's registered in `controller.frames`

    def load_session_from_start(self):
        chat_view = self.controller.frames["ChatView"]

        selected_folder = filedialog.askdirectory(
            initialdir="Character",
            title="Select a Session Folder to Load",
        )
        if not selected_folder:
            return  # Cancelled

        selected_folder = os.path.abspath(selected_folder)
        info_path = os.path.join(selected_folder, "session_info.json")

        if not os.path.exists(info_path):
            messagebox.showerror(
                "Invalid Folder",
                "Selected folder does not contain a session_info.json file."
            )
            return

        try:
            with open(info_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Failed", f"Could not read session_info.json:\n{e}")
            return

        self.controller.selected_character = session_data.get("llm_character", "")

        chat_view.load_session(session_data)
        self.controller.show_frame("ChatView")