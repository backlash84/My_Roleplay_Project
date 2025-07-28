import os
import customtkinter as ctk
import json

"""
app_controller.py

Defines the main RoleplayApp class, which acts as the central controller for the AI Roleplay Simulator.
Handles view registration, theming, settings loading, and navigation between UI screens.
"""
DEFAULT_SETTINGS_PATH = "config/advanced_settings.json"

class RoleplayApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Character Roleplay Simulator")
        self.geometry("900x800")

        # Stores currently selected character name (used by ChatView and others)
        self.selected_character = None

        # Theme defaults (overwritten later by settings loader)
        self.entry_bg_color = "#222222"
        self.accent_color = "#00ccff"
        self.text_color = "#ffffff"

        # Frame container for swapping between views
        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Dictionary of views registered with the controller
        self.frames = {}

    def register_view(self, name, frame):
        # Add a UI frame to the controller's registry and place it in the grid.
        self.frames[name] = frame
        frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, name):
        # Raise the specified frame to the front of the UI.
        self.frames[name].tkraise()

    def apply_theme_colors(self, bg_color, accent_color, text_color, entry_bg_color="#222222"):
        #Recursively applies color and font theming to all widgets in each registered view.
        # This is used when theme settings are loaded or updated.
        try:
            font = self.frames["AdvancedSettings"].get_ui_font()
        except Exception as e:
            print("[Theme Error] Could not retrieve font from AdvancedSettings:", e)
            font = ("Arial", 14)  # fallback default

        def apply_recursive(widget):
            # Apply styling based on widget type
            try:
                if isinstance(widget, ctk.CTkButton):
                    widget.configure(fg_color=accent_color, hover_color=accent_color, text_color=text_color, font=font)
                elif isinstance(widget, ctk.CTkSlider):
                    widget.configure(progress_color=accent_color, button_color=accent_color)
                elif isinstance(widget, ctk.CTkCheckBox):
                    widget.configure(border_color=accent_color, checkmark_color=accent_color, text_color=text_color, font=font)
                elif isinstance(widget, ctk.CTkLabel):
                    widget.configure(text_color=text_color, font=font)
                elif isinstance(widget, ctk.CTkEntry):
                    widget.configure(fg_color=entry_bg_color, text_color=text_color, font=font)
                elif isinstance(widget, ctk.CTkTextbox):
                    widget.configure(fg_color=entry_bg_color, text_color=text_color, font=font)
                elif isinstance(widget, ctk.CTkFrame):
                    widget.configure(fg_color=bg_color)
                elif isinstance(widget, ctk.CTkOptionMenu):
                    widget.configure(
                        fg_color=accent_color,
                        button_color=accent_color,
                        text_color=text_color,
                        text_color_disabled=text_color,
                        font=font
                    )
            except Exception as e:
                print(f"[Theme Error] Failed to style widget {widget}: {e}")

            for child in widget.winfo_children():
                apply_recursive(child)

        for frame in self.frames.values():
            apply_recursive(frame)

    def load_and_apply_settings(self):
        # Load saved settings (if they exist) and apply them globally to all views.
        # Also sets theme values on the controller for later use.
        if os.path.exists(DEFAULT_SETTINGS_PATH):
            with open(DEFAULT_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Apply settings to the AdvancedSettings screen
            self.frames["AdvancedSettings"].apply_settings(data)

            # Apply theme to all views after settings are loaded
            bg_color = data.get("theme_color", "#333333")
            accent_color = data.get("accent_color", "#00ccff")
            text_color = data.get("text_color", "#ffffff")
            entry_bg_color = data.get("entry_color", "#222222")

            for frame in self.frames.values():
                if hasattr(frame, "apply_theme_colors"):
                    try:
                        frame.apply_theme_colors()
                    except Exception as e:
                        print(f"[Warning] Failed to apply theme to {frame}: {e}")

    def start_chat(self, character_name):
        # Launch a new chat session using the given character
        # This calls ChatView.reset_chat() and shows the ChatView screen
        self.frames["ChatView"].reset_chat(character_name)
        self.show_frame("ChatView")

    def apply_theme_to_all_views(self):
        # Convenience method to re-apply theming to all frames with a theme updater
        # This is typically used after changing or reloading settings
        for frame in self.frames.values():
            if hasattr(frame, "apply_theme_colors"):
                frame.apply_theme_colors()

class CenteredFrame(ctk.CTkFrame):
    # A utility frame that centers its contents both horizontally and vertically
    def __init__(self, parent):
        super().__init__(parent)
        for i in range(3):
            self.grid_rowconfigure(i, weight=1)
            self.grid_columnconfigure(i, weight=1)