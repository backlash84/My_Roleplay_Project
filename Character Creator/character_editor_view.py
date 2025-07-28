import customtkinter as ctk
import os
import json
from base_settings_panel import BaseSettingsPanel
from scenarioprefix_panel import ScenarioPrefixPanel
from template_maker_panel import TemplateMakerPanel
from memory_maker_panel import MemoryMakerPanel
from finalizer import finalize_memories
from tkinter import messagebox



class CharacterEditorScreen(ctk.CTkFrame):
    def __init__(self, parent, controller, character_name, character_path):
        super().__init__(parent)
        self.controller = controller
        self.character_name = character_name
        self.character_path = character_path
        self.current_panel = None

        # Layout container
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar (Pink)
        sidebar = ctk.CTkFrame(self, width=150)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text=character_name, font=("Arial", 16)).pack(pady=20)

        ctk.CTkButton(sidebar, text="Base Settings", command=lambda: self.show_view("config")).pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(sidebar, text="Scenario & Prefix", command=lambda: self.show_view("scenarioprefix")).pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(sidebar, text="Memories", command=lambda: self.show_view("memories")).pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(sidebar, text="Template Maker", command=lambda: self.show_view("templatemaker")).pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(sidebar, text="Finalize", command=lambda: self.show_view("finalize")).pack(pady=10, fill="x", padx=10)
        ctk.CTkButton(sidebar, text="Back", command=self.controller.show_main_menu).pack(pady=40, fill="x", padx=10)

        # --- Content Area (Green)
        self.content_area = ctk.CTkFrame(self)
        self.content_area.grid(row=0, column=1, sticky="nsew")
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        self.current_view = None
        self.show_view("config")

    def show_view(self, view_name):
        if isinstance(self.current_panel, MemoryMakerPanel) and self.current_panel.has_unsaved_changes():
            result = messagebox.askyesno("Unsaved Changes", "You have unsaved changes.\nSave before switching panels?")
            if result:
                self.current_panel.save_current_memory()

        for widget in self.content_area.winfo_children():
            widget.destroy()

        if view_name == "config":
            config_path = os.path.join(self.character_path, "character_config.json")
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception as e:
                config_data = {}
                print(f"Error loading config: {e}")

            panel = BaseSettingsPanel(self.content_area, config_data, config_path)
            panel.grid(row=0, column=0, sticky="nsew")
            self.current_panel = panel

        elif view_name == "scenarioprefix":
            panel = ScenarioPrefixPanel(self.content_area, self.character_path)
            panel.grid(row=0, column=0, sticky="nsew")
            self.current_panel = panel

        elif view_name == "memories":
            panel = MemoryMakerPanel(self.content_area, self.character_path)
            panel.grid(row=0, column=0, sticky="nsew")
            self.current_panel = panel

        elif view_name == "templatemaker":
            panel = TemplateMakerPanel(self.content_area, self.character_path)
            panel.grid(row=0, column=0, sticky="nsew")
            self.current_panel = panel

        elif view_name == "finalize":
            panel = ctk.CTkFrame(self.content_area)
            panel.grid(row=0, column=0, sticky="nsew")

            label = ctk.CTkLabel(panel, text="Finalize View", font=("Arial", 20))
            label.grid(row=0, column=0, padx=20, pady=20)

            finalize_button = ctk.CTkButton(panel, text="Run Finalizer", command=self.run_finalizer)
            finalize_button.grid(row=1, column=0, padx=20, pady=10)

            self.current_panel = panel

    def run_finalizer(self):
        try:
            base_path = os.path.dirname(self.character_path)
            finalize_memories(self.character_name, base_path)
            messagebox.showinfo(
                "Success", f"Finalization complete for {self.character_name}."
            )
        except Exception as e:
            messagebox.showerror(
                "Finalization Error", f"An error occurred:\n{str(e)}"
            )