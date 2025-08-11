"""
advanced_settings.py

CustomTkinter view for modifying advanced configuration parameters used by the AI simulator.
Includes options for temperature, memory chunking, theme colors, model endpoint, and more.
User-defined settings can be saved and reloaded across sessions.
"""
import os
import json
import traceback
from tkinter import filedialog, messagebox
import customtkinter as ctk
from core.app_controller import CenteredFrame
DEFAULT_SETTINGS_PATH = "config/advanced_settings.json"

class AdvancedSettings(CenteredFrame):
    def __init__(self, parent, controller):
        """
        Initializes the Advanced Settings panel.

        This UI allows the user to adjust model behavior (temperature, penalties),
        memory search parameters, UI theming, and other global settings.
        """
        super().__init__(parent)
        self.controller = controller

        # Load saved settings inor use defaults
        self.settings_path = DEFAULT_SETTINGS_PATH
        self.settings = self.load_settings()

        container = ctk.CTkFrame(self)
        container.grid(row=1, column=1)
        container.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(container, text="Advanced Settings", font=("Arial", self.get_ui_font()[1] + 6)).grid(row=0, column=0, columnspan=3, pady=20)

        col1 = ctk.CTkFrame(container)
        col2 = ctk.CTkFrame(container)
        col3 = ctk.CTkFrame(container)
        col1.grid(row=1, column=0, padx=10, sticky="n")
        col2.grid(row=1, column=1, padx=10, sticky="n")
        col3.grid(row=1, column=2, padx=10, sticky="n")

        def add_labeled_entry(parent, label, default):
            ctk.CTkLabel(parent, text=label, font=self.get_ui_font()).pack()
            entry = ctk.CTkEntry(parent, width=180, font=self.get_ui_font())
            entry.insert(0, str(default))
            entry.pack(pady=(0, 10))
            return entry

        def add_slider_with_entry(parent, label, from_, to_, default, steps=100):
            ctk.CTkLabel(parent, text=label, font=self.get_ui_font()).pack()
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(pady=(0, 10))

            slider = ctk.CTkSlider(frame, from_=from_, to=to_, number_of_steps=steps)
            slider.pack(side="left", expand=True, fill="x", padx=(0, 5))

            entry = ctk.CTkEntry(frame, width=50, font=self.get_ui_font())
            entry.pack(side="right")
            entry.insert(0, str(default))

            def slider_changed(val):
                entry.delete(0, "end")
                entry.insert(0, f"{float(val):.2f}")

            def entry_changed(_):
                try:
                    value = float(entry.get())
                    value = max(min(value, to_), from_)
                    slider.set(value)
                except ValueError:
                    # Invalid input — restore to slider's current value
                    entry.delete(0, "end")
                    entry.insert(0, f"{slider.get():.2f}")

            slider.configure(command=slider_changed)
            entry.bind("<Return>", entry_changed)
            entry.bind("<FocusOut>", entry_changed)
            slider.set(default)
            return slider, entry

        def add_labeled_checkbox(parent, label, default):
            var = ctk.BooleanVar(value=default)
            chk = ctk.CTkCheckBox(parent, text=label, variable=var, font=self.get_ui_font())
            chk.pack(pady=(0, 10))
            return var

        # Column 1: Model + Memory
        self.max_tokens_entry = add_labeled_entry(col1, "Max Tokens", self.settings.get("max_tokens", 2048))
        self.no_token_limit_var = add_labeled_checkbox(col1, "No Token Limit", self.settings.get("no_token_limit", False))
        self.chat_history_entry = add_labeled_entry(col1, "Chat History Length", self.settings.get("chat_history_length", 10))
        self.chunk_entry = add_labeled_entry(col1, "Memory Chunks (Top K)", self.settings.get("top_k", 10))
        self.temp_slider, self.temp_entry = add_slider_with_entry(col1, "Temperature", 0.0, 1.5, self.settings.get("temperature", 0.7), 15)
        self.sim_thresh_slider, self.sim_thresh_entry = add_slider_with_entry(col1, "Similarity Threshold", 0.0, 1.0, self.settings.get("similarity_threshold", 0.7), 100)
        self.boost_slider, self.boost_entry = add_slider_with_entry(col1, "Memory Boost", 0.0, 3.0, self.settings.get("memory_boost", 0.5), 30)
        self.freq_penalty_slider, self.freq_penalty_entry = add_slider_with_entry(col1, "Frequency Penalty", 0.0, 2.0, self.settings.get("frequency_penalty", 0.0), 20)
        self.pres_penalty_slider, self.pres_penalty_entry = add_slider_with_entry(col1, "Presence Penalty", 0.0, 2.0, self.settings.get("presence_penalty", 0.0), 20)

        # Column 2: Display + Theme
        self.ui_theme_color_entry = add_labeled_entry(col2, "UI Theme Color (hex)", self.settings.get("theme_color", "#333333"))
        self.accent_color_entry = add_labeled_entry(col2, "Accent Color (hex)", self.settings.get("accent_color", "#00ccff"))
        self.entry_color_entry = add_labeled_entry(col2, "Entry BG Color (hex)", self.settings.get("entry_color", "#222222"))
        self.text_color_entry = add_labeled_entry(col2, "Text Color (hex)", self.settings.get("text_color", "#ffffff"))
        self.debug_color_entry = add_labeled_entry(col2, "Debug Text Color (hex)", self.settings.get("debug_color", "#ff0f0f"))
        self.text_size_entry = add_labeled_entry(col2, "Text Size", self.settings.get("text_size", 14))
        self.auto_scroll_var = add_labeled_checkbox(col2, "Auto-Scroll", self.settings.get("auto_scroll", True))

        # Column 3: API + Paths
        self.llm_url_entry = add_labeled_entry(col3, "LLM URL", self.settings.get("llm_url", "http://localhost:1234/v1/chat/completions"))
        self.model_entry = add_labeled_entry(col3, "Model Name", self.settings.get("model", "mistral-nemo-instruct-2407"))
        self.save_path_entry = add_labeled_entry(col3, "Save Path Override", self.settings.get("save_path", ""))
        self.clear_console_var = add_labeled_checkbox(col3, "Clear Console on Send", self.settings.get("clear_console_on_send", True))

        # Buttons for saving/loading settings profiles
        ctk.CTkButton(col3, text="Save Settings", font=self.get_ui_font(), command=self.save_settings_as).pack(pady=(0, 5))
        ctk.CTkButton(col3, text="Load Settings", font=self.get_ui_font(), command=self.load_settings_from_file).pack(pady=(0, 5))
        ctk.CTkButton(col3, text="Show Current Values (Debug)", font=self.get_ui_font(), command=self.print_current_values).pack(pady=(0, 5))
        ctk.CTkButton(col3, text="Back to Menu", font=self.get_ui_font(), command=lambda: controller.show_frame("StartMenu")).pack(pady=(0, 20))


    def get_ui_font(self):
        settings = self.controller.frames.get("AdvancedSettings")
        size = settings.get_text_size() if settings else 14
        return ("Arial", size)

    def get_temperature(self):
        try:
            return round(float(self.temp_entry.get()), 2)
        except (ValueError, TypeError):
            return 0.7
    def get_memory_chunk_limit(self):
        try:
            return max(1, int(self.chunk_entry.get()))
        except (ValueError, TypeError):
            return 10
    def get_similarity_threshold(self):
        try:
            return round(float(self.sim_thresh_entry.get()), 2)
        except (ValueError, TypeError):
            return 0.7
    def get_memory_boost(self):
        try:
            return round(float(self.boost_entry.get()), 2)
        except (ValueError, TypeError):
            return 0.5
    def get_text_size(self): return int(self.text_size_entry.get())
    def get_debug_color(self): return self.debug_color_entry.get().strip()
    def get_theme_color(self): return self.ui_theme_color_entry.get().strip()
    def get_llm_url(self): return self.llm_url_entry.get().strip()
    def get_model_name(self): return self.model_entry.get().strip()
    def get_max_tokens(self):
        if self.get_no_token_limit():
            return None
        try:
            return int(self.max_tokens_entry.get())
        except (ValueError, TypeError):
            messagebox.showwarning("Invalid Input", "Max tokens must be a number.")
            return 2048
    def get_no_token_limit(self): return self.no_token_limit_var.get()
    def get_frequency_penalty(self):
        try:
            return round(float(self.freq_penalty_entry.get()), 2)
        except (ValueError, TypeError):
            return 0.0
    def get_presence_penalty(self):
        try:
            return round(float(self.pres_penalty_entry.get()), 2)
        except (ValueError, TypeError):
            return 0.0
    def get_auto_scroll(self): return self.auto_scroll_var.get()
    def get_save_path(self): return self.save_path_entry.get().strip()
    def get_accent_color(self): return self.accent_color_entry.get().strip()
    def get_text_color(self): return self.text_color_entry.get().strip()

    def get_chat_history_length(self):
        try:
            return max(0, int(self.chat_history_entry.get()))
        except (ValueError, TypeError):
            return 0

    def save_settings_as(self):
        """
        Opens a file dialog and saves the current settings as a JSON profile.
        Also saves a copy to the default path to persist changes for next launch.
        """
        profile_dir = "config/settings_profiles"
        os.makedirs(profile_dir, exist_ok=True)

        file_path = filedialog.asksaveasfilename(
            initialdir=profile_dir,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            title="Save Settings Profile"
        )
        if not file_path:
            return

        settings = self.get_all_settings()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.get_all_settings(), f, indent=2)

        # Also save to default so it's applied next launch
        with open(DEFAULT_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.get_all_settings(), f, indent=2)

    def load_settings(self):
        """
        Loads the default settings from disk if available.
        Returns an empty dict if file is empty or unreadable.
        """
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    print("[Warning] Settings file is empty. Using default settings.")
                    return {}

                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    messagebox.showerror("Settings Error", "Your settings file is corrupted.\nDefault values will be used.")
                    return {}
        return {}

    def load_settings_from_file(self):
        """
        Opens a file dialog to load a previously saved settings profile (.json).
        Applies the loaded settings to the Advanced Settings panel and updates
        the global UI theme and model parameters accordingly.

        Typically used to quickly switch between user-defined configurations.
        """
        profile_dir = "config/settings_profiles"
        os.makedirs(profile_dir, exist_ok=True)

        file_path = filedialog.askopenfilename(
            initialdir=profile_dir,
            filetypes=[("JSON Files", "*.json")],
            title="Load Settings Profile"
        )
        if not file_path:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        self.apply_settings(settings)

        # Save this as the new default for next launch
        with open(DEFAULT_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def get_all_settings(self):
        """
        Collects all user-defined settings from the UI into a dictionary.

        Returns:
            dict: All advanced settings, used for saving or injecting into model prompts.
        """
        max_tokens = self.get_max_tokens()
        return {
            "no_token_limit": self.get_no_token_limit(),
            "chat_history_length": self.get_chat_history_length(),
            "temperature": self.get_temperature(),
            "top_k": self.get_memory_chunk_limit(),
            "similarity_threshold": self.get_similarity_threshold(),
            "memory_boost": self.get_memory_boost(),
            "text_size": self.get_text_size(),
            "debug_color": self.get_debug_color(),
            "theme_color": self.get_theme_color(),
            "accent_color": self.get_accent_color(),
            "entry_color": self.entry_color_entry.get().strip(),
            "text_color": self.get_text_color(),
            "llm_url": self.get_llm_url(),
            "model": self.get_model_name(),
            "max_tokens": max_tokens,
            "frequency_penalty": self.get_frequency_penalty(),
            "presence_penalty": self.get_presence_penalty(),
            "auto_scroll": self.get_auto_scroll(),
            "save_path": self.get_save_path(),
            "clear_console_on_send": self.clear_console_var.get()
        }

    def set_slider_and_entry(self, slider, entry, value):
        try:
            num = float(value)
        except (ValueError, TypeError):
            num = 0.0
        slider.set(num)
        entry.delete(0, "end")
        entry.insert(0, f"{num:.2f}")

    def apply_settings(self, data):
        """
        Apply a settings dictionary to the UI.

        This is called when loading saved profiles or restoring defaults. It also
        applies the visual theming and updates controller-level shared colors.
        """
        try:
            max_tokens = data.get("max_tokens") or 2048
            self.max_tokens_entry.delete(0, "end")
            self.max_tokens_entry.insert(0, str(max_tokens))

            self.chunk_entry.delete(0, "end")
            self.chunk_entry.insert(0, data.get("top_k", 10))

            self.set_slider_and_entry(self.temp_slider, self.temp_entry, data.get("temperature", 0.7))
            self.set_slider_and_entry(self.sim_thresh_slider, self.sim_thresh_entry, data.get("similarity_threshold", 0.7))
            self.set_slider_and_entry(self.boost_slider, self.boost_entry, data.get("memory_boost", 0.5))
            self.set_slider_and_entry(self.freq_penalty_slider, self.freq_penalty_entry, data.get("frequency_penalty", 0.0))
            self.set_slider_and_entry(self.pres_penalty_slider, self.pres_penalty_entry, data.get("presence_penalty", 0.0))

            self.text_size_entry.delete(0, "end")
            self.text_size_entry.insert(0, data.get("text_size", 14))

            self.ui_theme_color_entry.delete(0, "end")
            self.ui_theme_color_entry.insert(0, data.get("theme_color", "#333333"))

            self.accent_color_entry.delete(0, "end")
            self.accent_color_entry.insert(0, data.get("accent_color", "#00ccff"))

            self.entry_color_entry.delete(0, "end")
            self.entry_color_entry.insert(0, data.get("entry_color", "#222222"))

            self.text_color_entry.delete(0, "end")
            self.text_color_entry.insert(0, data.get("text_color", "#ffffff"))

            self.debug_color_entry.delete(0, "end")
            self.debug_color_entry.insert(0, data.get("debug_color", "#ff0f0f"))

            self.llm_url_entry.delete(0, "end")
            self.llm_url_entry.insert(0, data.get("llm_url", "http://localhost:1234/v1/chat/completions"))

            self.model_entry.delete(0, "end")
            self.model_entry.insert(0, data.get("model", "mistral-nemo-instruct-2407"))

            self.save_path_entry.delete(0, "end")
            self.save_path_entry.insert(0, data.get("save_path", ""))

            self.no_token_limit_var.set(data.get("no_token_limit", False))
            self.auto_scroll_var.set(data.get("auto_scroll", True))
            self.clear_console_var.set(data.get("clear_console_on_send", True))

            # Update controller theme values FIRST
            self.controller.entry_bg_color = data.get("entry_color", "#222222")
            self.controller.accent_color = data.get("accent_color", "#00ccff")
            self.controller.text_color = data.get("text_color", "#ffffff")

            # Apply UI theme
            self.controller.apply_theme_colors(
                bg_color=data.get("theme_color", "#333333"),
                accent_color=self.controller.accent_color,
                text_color=self.controller.text_color,
                entry_bg_color=self.controller.entry_bg_color
            )

            # Update chat colors
            self.controller.apply_theme_to_all_views()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply settings:\n{e}")

    def print_current_values(self):
        print("\n=== Current Advanced Settings ===")
        for key in [
            "temperature", "memory_chunk_limit", "no_token_limit", "similarity_threshold", "memory_boost", "text_size",
            "debug_color", "user_color", "theme_color", "llm_url", "model_name",
            "max_tokens", "frequency_penalty", "presence_penalty",
            "auto_scroll", "save_path", "clear_console_on_send"
        ]:
            print(f"{key}:", getattr(self, f"get_{key}")())
        print("=== End ===\n")

