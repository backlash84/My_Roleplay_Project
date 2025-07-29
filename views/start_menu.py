import os
import customtkinter as ctk
from tkinter import messagebox, filedialog

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
            title="Select a Session Folder to Load"
        )
        if not selected_folder:
            return  # Cancelled

        # Normalize path
        selected_folder = os.path.abspath(selected_folder)

        # Make sure it's under a Character/*/Sessions/* path
        try:
            # Split the full path
            parts = selected_folder.split(os.sep)

            # We want to find: .../Character/{char_name}/Sessions/{session_name}
            if "Character" not in parts or "Sessions" not in parts:
                raise ValueError

            char_index = parts.index("Character") + 1
            sessions_index = parts.index("Sessions")

            if sessions_index - char_index != 1:
                raise ValueError  # Sessions is not directly inside character folder

            char_name = parts[char_index]
            session_name = parts[sessions_index + 1]
        except (ValueError, IndexError):
            messagebox.showerror("Invalid Folder", "Selected folder must be inside a Character/<name>/Sessions/<session> path.")
            return

        session_data = {
            "llm_character": char_name,
            "user_character": self.controller.user_character_name or "",
            "session_name": session_name,
            "scenario_file": "",
            "prefix_file": ""
        }

        chat_view.load_session(session_data)
        self.controller.show_frame("ChatView")