import customtkinter as ctk
import json
import os
from tkinter import messagebox, filedialog
from transformers import AutoTokenizer


class BaseSettingsPanel(ctk.CTkFrame):
    def __init__(self, parent, config_data, config_path):
        super().__init__(parent)
        self.config_path = config_path

        self.entries = {}

        # Fields to keep
        fields = [
            ("Name", "name"),
            ("Author", "author"),
            ("Text Colour", "text_color"),
            ("Notes", "notes")
        ]

        visibility_options = ["shared", "private", "system_only"]

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll_frame = ctk.CTkScrollableFrame(self, width=600)
        scroll_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=(10, 0))
        scroll_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(scroll_frame, text="Character Base Settings", font=("Arial", 20)).grid(row=0, column=0, columnspan=2, pady=20)

        # Standard input fields
        for idx, (label_text, field_key) in enumerate(fields, start=1):
            ctk.CTkLabel(scroll_frame, text=label_text + ":", anchor="e", width=140).grid(row=idx, column=0, padx=10, pady=5, sticky="e")
            entry = ctk.CTkEntry(scroll_frame, width=400)
            entry.insert(0, config_data.get(field_key, ""))
            entry.grid(row=idx, column=1, padx=10, pady=5, sticky="w")
            self.entries[field_key] = entry

        # Visibility dropdown
        ctk.CTkLabel(scroll_frame, text="Visibility:", anchor="e", width=140).grid(row=idx + 1, column=0, padx=10, pady=5, sticky="e")
        self.visibility_dropdown = ctk.CTkOptionMenu(scroll_frame, values=visibility_options)
        self.visibility_dropdown.set(config_data.get("visibility", "shared"))
        self.visibility_dropdown.grid(row=idx + 1, column=1, padx=10, pady=5, sticky="w")

        # Character information text box
        ctk.CTkLabel(scroll_frame, text="Character Information:", anchor="ne", width=140).grid(row=idx + 2, column=0, padx=10, pady=5, sticky="ne")
        self.character_info_text = ctk.CTkTextbox(scroll_frame, width=400, height=160, wrap="word")
        self.character_info_text.insert("1.0", config_data.get("character_information", ""))
        self.character_info_text.grid(row=idx + 2, column=1, padx=10, pady=5, sticky="w")

        # Save/Load buttons
        button_row = ctk.CTkFrame(self)
        button_row.grid(row=1, column=0, columnspan=2, pady=20)

        ctk.CTkButton(button_row, text="Save", width=100, command=self.save_config).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Load", width=100, command=self.load_config).pack(side="left", padx=10)

    def save_config(self):
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        data["visibility"] = self.visibility_dropdown.get()
        data["character_information"] = self.character_info_text.get("1.0", "end").strip()

        # --- Token counting ---
        try:
            tokenizer = AutoTokenizer.from_pretrained("Intel/neural-chat-7b-v3-1", trust_remote_code=True)
            name_tokens = tokenizer.encode(data["name"], add_special_tokens=False)
            info_tokens = tokenizer.encode(data["character_information"], add_special_tokens=False)
            total_tokens = len(name_tokens) + len(info_tokens)
            data["token_estimate"] = total_tokens
        except Exception as e:
            total_tokens = -1
            data["token_estimate"] = -1

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if total_tokens != -1:
                messagebox.showinfo("Saved", f"Character configuration saved.\nEstimated token count: {total_tokens}")
            else:
                messagebox.showinfo("Saved", "Character configuration saved.\nToken count could not be estimated.")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Error saving config:\n{e}")

    def load_config(self):
        folder_path = filedialog.askdirectory(
            title="Select Character Folder",
            initialdir=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Character"))
        )

        if not folder_path:
            return

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
        self.character_info_text.delete("1.0", "end")
        self.character_info_text.insert("1.0", config_data.get("character_information", ""))

        self.config_path = file_path