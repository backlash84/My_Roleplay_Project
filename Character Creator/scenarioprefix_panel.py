import customtkinter as ctk
import os
from tkinter import filedialog, messagebox
import json

class ScenarioPrefixPanel(ctk.CTkFrame):
    def __init__(self, parent, character_path):
        super().__init__(parent)
        self.character_path = character_path
        self.config_path = os.path.join(character_path, "character_config.json")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # SCENARIO SECTION
        ctk.CTkLabel(self, text="Scenario", font=("Arial", 16)).grid(row=0, column=0, pady=(10, 0), sticky="w")
        self.scenario_box = ctk.CTkTextbox(self, width=800, height=250)
        self.scenario_box.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        scenario_button_row = ctk.CTkFrame(self)
        scenario_button_row.grid(row=2, column=0, pady=5)
        ctk.CTkButton(scenario_button_row, text="Load", command=self.load_scenario).pack(side="left", padx=5)
        ctk.CTkButton(scenario_button_row, text="Save", command=self.save_scenario).pack(side="left", padx=5)
        ctk.CTkButton(scenario_button_row, text="Apply", command=self.apply_scenario).pack(side="left", padx=5)

        # PREFIX SECTION
        ctk.CTkLabel(self, text="Prefix", font=("Arial", 16)).grid(row=3, column=0, pady=(20, 0), sticky="w")
        self.prefix_box = ctk.CTkTextbox(self, width=800, height=250)
        self.prefix_box.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")

        prefix_button_row = ctk.CTkFrame(self)
        prefix_button_row.grid(row=5, column=0, pady=5)
        ctk.CTkButton(prefix_button_row, text="Load", command=self.load_prefix).pack(side="left", padx=5)
        ctk.CTkButton(prefix_button_row, text="Save", command=self.save_prefix).pack(side="left", padx=5)
        ctk.CTkButton(prefix_button_row, text="Apply", command=self.apply_prefix).pack(side="left", padx=5)

        # Preload scenario/prefix from character_config.json
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.scenario_box.insert("1.0", config.get("scenario", ""))
            self.prefix_box.insert("1.0", config.get("prefix_instructions", ""))
        except Exception as e:
            print(f"[Warning] Could not preload scenario/prefix: {e}")

    # --- SCENARIO ACTIONS ---
    def load_scenario(self):
        path = filedialog.askopenfilename(initialdir=os.path.join(self.character_path, "Scenarios"), title="Load Scenario", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.scenario_box.delete("1.0", "end")
                self.scenario_box.insert("1.0", f.read())

    def save_scenario(self):
        path = filedialog.asksaveasfilename(initialdir=os.path.join(self.character_path, "Scenarios"), defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.scenario_box.get("1.0", "end").strip())

    def apply_scenario(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["scenario"] = self.scenario_box.get("1.0", "end").strip()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Scenario Applied", "Scenario applied to character_config.json.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply scenario:\n{e}")

    # --- PREFIX ACTIONS ---
    def load_prefix(self):
        path = filedialog.askopenfilename(initialdir=os.path.join(self.character_path, "Prefix"), title="Load Prefix", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.prefix_box.delete("1.0", "end")
                self.prefix_box.insert("1.0", f.read())

    def save_prefix(self):
        path = filedialog.asksaveasfilename(initialdir=os.path.join(self.character_path, "Prefix"), defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.prefix_box.get("1.0", "end").strip())

    def apply_prefix(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["prefix_instructions"] = self.prefix_box.get("1.0", "end").strip()
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Prefix Applied", "Prefix applied to character_config.json.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply prefix:\n{e}")