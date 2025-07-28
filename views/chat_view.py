import json
import os
import threading
import faiss
import re
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from nltk.stem import WordNetLemmatizer
from tkinter import messagebox, filedialog
import customtkinter as ctk
from utils.memory_utils import retrieve_relevant_memories
from utils.session_utils import load_session
from utils.api_utils import call_llm_api
from core.conversation_service import ConversationService
from utils.debug_utils import generate_basic_debug_report, generate_advanced_debug_report

class ChatView(ctk.CTkFrame):
    def toggle_debug_mode(self):
        self.debug_mode = self.debug_toggle_var.get()

    def __init__(self, parent, controller):
        self.thinking_label = None
        self._thinking_anim_id = None
        self._thinking_dots = 0
        self.show_memory_debug_var = ctk.BooleanVar(value=False)
        self.editing_reply = False
        self.debug_toggle_var = ctk.BooleanVar(value=False)
        self.debug_mode = self.debug_toggle_var.get()  # Sync immediately
        self.conversation_history = []
        self.conversation_service = ConversationService(controller)

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

        # Top row for right-aligned retry button
        top_button_row = ctk.CTkFrame(inner)
        top_button_row.pack(fill="x", pady=(5, 0))

        font=self.get_ui_font()
        ctk.CTkButton(top_button_row, text="Try Again", width=100, font=self.get_ui_font(), command=self.retry_last_response).pack(side="right", padx=10) 

        self.edit_button = ctk.CTkButton(top_button_row, text="Edit Reply", width=100, font=self.get_ui_font(), command=self.toggle_edit_last_reply)
        self.edit_button.pack(side="right", padx=10)
        ctk.CTkButton(top_button_row, text="Back", width=100, font=self.get_ui_font(), command=self.confirm_back_to_main).pack(side="left", padx=10)

        entry_bg_color = controller.entry_bg_color
        accent_color = controller.accent_color  # new line
        text_color = "#ffffff"  # default fallback

        # Load saved chat colors from settings
        user_color = controller.frames.get("AdvancedSettings")
        if user_color:
            user_color = user_color.get_user_color()
        else:
            user_color = "#00ccff"

        debug_color = controller.frames.get("AdvancedSettings")
        if debug_color:
            debug_color = debug_color.get_debug_color()
        else:
            debug_color = "#ff0f0f"

        entry_bg_color = controller.entry_bg_color
        text_color = controller.text_color  # optional, if you also want this dynamic
        accent_color = controller.accent_color  # just for reference

        self.chat_display = ctk.CTkTextbox(inner, height=350, width=600, font=self.get_ui_font(), wrap="word",
                                           fg_color=entry_bg_color, text_color=text_color,
                                           border_color=accent_color, border_width=2)
        self.chat_display.pack(pady=10)
        self.chat_display.configure(state="disabled")

        self.chat_display.tag_config("thinking_tag", foreground="#AAAAAA")


        self.entry = ctk.CTkTextbox(inner, width=500, height=120, font=self.get_ui_font(), wrap="word",
                                    fg_color=entry_bg_color, text_color=text_color,
                                    border_color=accent_color, border_width=2)
        self.entry.pack(pady=(0, 10))

        # Optional: keep bot color as default
        self.character_color = "#ffeb0f"  # default fallback if none is loaded yet

        # Apply tag styles
        self.chat_display.tag_config("user", foreground=user_color)
        self.chat_display.tag_config("bot", foreground=self.character_color)
        self.chat_display.tag_config("debug", foreground=debug_color)

        # Create a horizontal row of buttons
        button_row = ctk.CTkFrame(inner)
        button_row.pack(pady=(0, 10))

        ctk.CTkButton(button_row, text="Send", width=100, font=self.get_ui_font(), command=self.send_message).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Save", width=100, font=self.get_ui_font(), command=self.save_session).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Load", width=100, font=self.get_ui_font(), command=lambda: load_session(self)).pack(side="left", padx=5)

        self.debug_toggle_var = ctk.BooleanVar(value=False)
        self.debug_toggle = ctk.CTkCheckBox(
            inner,
            text="Show memory debug",
            font=self.get_ui_font(),
            variable=self.debug_toggle_var,
            command=self.toggle_debug_mode
        )

        self.debug_toggle.pack(pady=(5, 10))

        self.chat_initialized = False
        self.prefix = ""
        self.scenario = ""
        self.memory_index = None
        self.memory_mapping = []
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.lemmatizer = WordNetLemmatizer()
        self.last_prompt = None

    def set_entry_buttons_state(self, state):
        for child in self.entry.master.winfo_children():
            if isinstance(child, ctk.CTkButton):
                child.configure(state=state)

    def get_ui_font(self):
            settings = self.controller.frames.get("AdvancedSettings")
            size = settings.get_text_size() if settings else 14
            return ("Arial", size)

    def print_memory_debug(self):
        payload = getattr(self, "last_payload_used", {})
        memory_debug_lines = getattr(self, "memory_debug_lines", [])
        selected_memories = getattr(self, "selected_memories", [])
        if self.debug_mode:
            debug_text = generate_basic_debug_report(payload, memory_debug_lines, selected_memories)
            print(debug_text)
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", debug_text + "\n", "debug")
            self.chat_display.configure(state="disabled")

    def retry_last_response(self):
        if not hasattr(self, "last_built_prompt") or not hasattr(self, "last_payload_used") or not self.last_built_prompt or not self.last_payload_used:
            messagebox.showinfo("Retry Unavailable", "Retry is only available after sending a new message.")
            return
        if not hasattr(self, "last_built_prompt") or not hasattr(self, "last_payload_used"):
            print("[Retry] Missing saved prompt or payload. Cannot retry.")
            return

        self.chat_display.configure(state="normal")
        content = self.chat_display.get("1.0", "end")

        # Attempt to remove the last AI reply block
        lines = content.strip().split("\n")
        char_label = f"{self.controller.selected_character}:"

        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith(char_label):
                lines = lines[:i]
                break
        else:
            print("[Retry] Warning: Could not find AI label to remove.")
            return

        # Trim the conversation history to remove the last assistant message
        for i in range(len(self.conversation_history) - 1, -1, -1):
            if self.conversation_history[i]["role"] == "assistant":
                self.conversation_history = self.conversation_history[:i]
                break

        self.render_conversation_to_display()

        # Launch a retry using the last used prompt and payload (same vector memory, same input)
        print("[Retry] Attempting to retry previous prompt.")
        threading.Thread(
            target=lambda: self._handle_llm_response(
                self.last_built_prompt,
                self.last_payload_used,
                self.last_prompt  # this is just for debug tagging
            )
        ).start()

    def toggle_edit_last_reply(self):
        self.chat_display.configure(state="normal")
        content = self.chat_display.get("1.0", "end").strip().split("\n")

        char_label = f"{self.controller.selected_character}:"

        if not self.editing_reply:
            # Enter editing mode: find and highlight last AI line
            for i in range(len(content) - 1, -1, -1):
                if content[i].startswith(char_label):
                    self.last_ai_line_index = i
                    break
            else:
                self.chat_display.configure(state="disabled")
                messagebox.showinfo("No AI Reply Found", "There is no previous AI message to edit.")
                return

            # Put entire content back in editable state
            # Highlight just the last AI reply line for editing
            start = f"{self.last_ai_line_index + 1}.0"
            end = f"{self.last_ai_line_index + 1}.end"
            self.chat_display.tag_add("edit", start, end)
            self.chat_display.tag_config("edit", background="#444444")  # subtle highlight
            self.chat_display.mark_set("insert", end)
            self.chat_display.see(start)
            self.editing_reply = True
            self.edit_button.configure(text="Save Edit")
            return

        else:
            # Save edits: update internal state and restore tag
            edited_reply = self.chat_display.get(f"{self.last_ai_line_index + 1}.0", f"{self.last_ai_line_index + 1}.end").strip()

            self.chat_display.tag_remove("edit", f"{self.last_ai_line_index + 1}.0", f"{self.last_ai_line_index + 1}.end")
            self.chat_display.tag_add("bot", f"{self.last_ai_line_index + 1}.0", f"{self.last_ai_line_index + 1}.end")
            self.chat_display.configure(state="disabled")

            self.editing_reply = False
            self.edit_button.configure(text="Edit Reply")

            # Update conversation history with the edited assistant reply
            for i in range(len(self.conversation_history) - 1, -1, -1):
                if self.conversation_history[i]["role"] == "assistant":
                    self.conversation_history[i]["content"] = edited_reply
                    break

    def apply_theme_colors(self):
        entry_bg_color = self.controller.entry_bg_color
        text_color = self.controller.text_color
        accent_color = self.controller.accent_color
        font_size = self.controller.frames["AdvancedSettings"].get_text_size()
        font = ("Arial", font_size)

        self.chat_display.configure(
            fg_color=entry_bg_color,
            text_color=text_color,
            border_color=accent_color,
            font=font
        )
        self.entry.configure(
            fg_color=entry_bg_color,
            text_color=text_color,
            border_color=accent_color,
            font=font
        )

    def save_session(self):
        session_dir = "Sessions"
        os.makedirs(session_dir, exist_ok=True)

        # Warn user before proceeding
        confirm = messagebox.askyesno(
            "Confirm Save",
            "Warning: Saved bot posts cannot be retried after reloading.\n\n"
            "Continue with saving?"
        )
        if not confirm:
            return

        save_path = self.controller.frames["AdvancedSettings"].get_save_path().strip()

        if save_path:
            file_path = save_path
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json",
                initialdir=session_dir,
                filetypes=[("JSON Files", "*.json")],
                title="Save Session"
            )
            if not file_path:
                return

        session_data = {
            "character": self.controller.selected_character,
            "chat": self.chat_display.get("1.0", "end").strip(),
            "scenario": self.scenario,
            "prefix": self.prefix,
            "conversation_history": self.conversation_history
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2)

    def confirm_back_to_main(self):
        if messagebox.askyesno("Return to Main Menu", "Are you sure you want to return to the main menu? Unsaved progress will be lost."):
            self.controller.show_frame("StartMenu")

    def send_message(self):
        scenario_ui = self.controller.frames["CharacterSettings"].scenario_box.get("1.0", "end")
        prefix_ui = self.controller.frames["CharacterSettings"].prefix_box.get("1.0", "end")

        settings = self.controller.frames["AdvancedSettings"]
        settings_data = settings.get_all_settings()

        user_input = self.entry.get("1.0", "end").strip()
        if not user_input:
            return

        self.last_prompt = user_input
        self.entry.delete("1.0", "end")  # delete AFTER getting text
        self.entry.configure(state="disabled")

        self.set_entry_buttons_state("disabled")

        if not self.thinking_label:
            self.thinking_label = ctk.CTkLabel(self.entry.master, text="Thinking", font=self.get_ui_font())
            self.thinking_label.pack(pady=(0, 5))

        self._thinking_dots = 0
        self._animate_thinking()

        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"You: {user_input}\n\n", "user")  # single insert with spacing
        self.chat_display.configure(state="disabled")

        if settings_data.get("auto_scroll", True):
            self.chat_display.see("end")

        self.conversation_history.append({"role": "user", "content": user_input})

        # Enforce max rolling memory size
        max_history = self.controller.frames["AdvancedSettings"].get_chat_history_length()
        if max_history > 0 and len(self.conversation_history) > max_history * 2:
            # Multiply by 2 because it's alternating user/assistant pairs
            self.conversation_history = self.conversation_history[-max_history * 2:]

        threading.Thread(
            target=self.fetch_and_display_reply,
            args=(user_input, settings_data, scenario_ui, prefix_ui)
        ).start()

    def fetch_and_display_reply(self, user_message, settings_data, scenario_ui, prefix_ui):
        # Clear console display if "clear console on send" is toggled.
        os.system("cls" if os.name == "nt" else "clear")

        self.last_prompt = user_message  # this is okay to set early

        # Retrieve memories with optional debug scoring
        memory_objects, memory_debug_lines = retrieve_relevant_memories(
            user_message,
            self.memory_index,
            self.memory_mapping,
            self.embedder,
            self.lemmatizer,
            settings_data,
            self.debug_mode
        )

        # Use the full memory dicts in the prompt builder
        prompt = self.conversation_service.build_prompt(
            user_message, memory_objects, self.scenario, self.prefix
        )

        # Build LLM payload
        payload = self.conversation_service.build_payload(prompt, settings_data)

        # NOW you can safely store the retry data
        self.last_built_prompt = prompt
        self.last_payload_used = payload

        # Save debug data for later display
        self.memory_debug_lines = memory_debug_lines
        print("\n=== RAW MEMORY OBJECTS ===")
        print(memory_objects)
        print("=========================\n")

        self.selected_memories = [m["memory_id"] for m in memory_objects if "memory_id" in m]

        # Convert prompt into OpenAI-style message list
        messages, filtered_history = self.conversation_service.build_chat_messages(
            self.conversation_history,
            self.scenario,
            self.prefix,
            memory_objects
        )
        payload["messages"] = messages

        # Print full console debug if enabled
        if self.debug_mode:
            debug_text_console = generate_advanced_debug_report(
                settings_data=settings_data,
                scenario_sent=self.scenario,
                prefix_sent=self.prefix,
                memory_debug_lines=self.memory_debug_lines,
                selected_memories=self.selected_memories,
                conversation_history=filtered_history,
                prompt_payload=payload,
                raw_prompt=prompt,
                scenario_ui=scenario_ui,
                prefix_ui=prefix_ui
            )
            print(debug_text_console)

        # Launch async call to LLM
        thread = threading.Thread(
            target=lambda: self._handle_llm_response(prompt, payload, user_message)
        )
        thread.start()

    def _handle_llm_response(self, prompt, payload, user_message):
        reply = self.conversation_service.fetch_reply(
            payload, self.conversation_history, prompt, debug_mode=self.debug_mode
        )
        self.after(0, lambda: self._display_reply(reply))
        self.conversation_history.append({"role": "assistant", "content": reply})
        print("[DEBUG] Raw reply returned by LLM:", repr(reply))

    def _display_reply(self, reply):
        self.print_memory_debug()

        # Remove thinking line or tag
        try:
            self.chat_display.configure(state="normal")

            # Remove (Thinking...) if it exists
            index = self.chat_display.search("(Thinking...)", "1.0", "end")
            if index:
                line_end = f"{index} lineend+1c"
                self.chat_display.delete(index, line_end)

            # Remove tag range if defined
            self.chat_display.delete("thinking_tag.first", "thinking_tag.last")
        except Exception:
            pass

        # Stop spinner animation
        if self._thinking_anim_id:
            self.after_cancel(self._thinking_anim_id)
            self._thinking_anim_id = None

        # Remove label
        if self.thinking_label:
            self.thinking_label.destroy()
            self.thinking_label = None

        # Insert reply text
        clean_reply = reply.strip()
        if not clean_reply:
            clean_reply = "[No response received.]"

        self.chat_display.insert("end", f"{self.controller.selected_character}: {clean_reply}\n\n", "bot")
        self.chat_display.configure(state="disabled")

        # Scroll if setting enabled
        if self.controller.frames["AdvancedSettings"].get_auto_scroll():
            self.chat_display.see("end")

        self.entry.configure(state="normal")
        self.set_entry_buttons_state("normal")

    def tkraise(self, aboveThis=None):
        super().tkraise(aboveThis)
        self.debug_mode = self.debug_toggle_var.get()
        if not self.chat_initialized:
            self.load_character_assets()
            self.chat_initialized = True

    def load_character_assets(self, force_reload=False):
        if self.chat_initialized and not force_reload:
            return

        char_name = self.controller.selected_character
        if not char_name:
            return

        path = os.path.join("Character", char_name)
        config_path = os.path.join(path, "character_config.json")
        index_path = os.path.join(path, "memory_index.faiss")
        mapping_path = os.path.join(path, "memory_mapping.json")

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.character_color = data.get("text_color", "#ffeb0f")
                self.chat_display.tag_config("bot", foreground=self.character_color)
                if force_reload or not self.prefix:
                    self.prefix = data.get("prefix_instructions", "")
                if force_reload or not self.scenario:
                    self.scenario = data.get("scenario", "")

        if os.path.exists(index_path) and os.path.exists(mapping_path):
            self.memory_index = faiss.read_index(index_path)
            with open(mapping_path, "r", encoding="utf-8") as f:
                self.memory_mapping = json.load(f)

        if not self.chat_display.get("1.0", "end").strip():
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"--- {char_name} loaded ---\nScenario: {self.scenario}\n\n")
            self.chat_display.configure(state="disabled")

    def render_conversation_to_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")

        for entry in self.conversation_history:
            role = entry.get("role")
            content = entry.get("content", "")
            tag = "user" if role == "user" else "bot"
            label = "You" if role == "user" else self.controller.selected_character
            self.chat_display.insert("end", f"{label}: ", tag)
            self.chat_display.insert("end", content.strip() + "\n\n", tag)

        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")  # Auto-scroll to most recent message

    def reset_chat(self, character_name):
        self.controller.selected_character = character_name
        self.chat_initialized = False
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self.entry.delete("1.0", "end")
        self.load_character_assets(force_reload=True)

        # Trim or clear history after reset
        max_history = self.controller.frames["AdvancedSettings"].get_chat_history_length()
        if max_history > 0 and len(self.conversation_history) > max_history * 2:
            self.conversation_history = self.conversation_history[-max_history * 2:]
        else:
            self.conversation_history.clear()

        self.last_prompt = None

    def _animate_thinking(self):
        if not self.thinking_label:
            return

        dots = "." * (self._thinking_dots % 4)
        self.thinking_label.configure(text=f"Thinking{dots}")
        self._thinking_dots += 1
        self._thinking_anim_id = self.after(500, self._animate_thinking)