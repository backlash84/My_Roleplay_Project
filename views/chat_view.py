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
        super().__init__(parent)
        self.controller = controller
        self.thinking_label = None

        # --- Core state ---
        self.chat_initialized = False
        self.editing_reply = False
        self._thinking_anim_id = None
        self._thinking_dots = 0
        self.last_prompt = None
        self.conversation_history = []
        self.memory_index = None
        self.memory_mapping = []
        self.prefix = ""
        self.scenario = ""
        self.llm_character = None  # Will be loaded from session
        self.user_character = None  # Will be loaded from session

        # --- Services ---
        self.conversation_service = ConversationService(controller)
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.lemmatizer = WordNetLemmatizer()

        # --- Theme + Colors ---
        font = self.get_ui_font()
        accent_color = controller.accent_color
        entry_bg_color = controller.entry_bg_color
        text_color = controller.text_color

        # --- Fallback character/user colors ---
        self.character_color = "#ffeb0f"
        self.user_color = controller.frames.get("AdvancedSettings").get_user_color() if controller.frames.get("AdvancedSettings") else "#00ccff"
        self.debug_color = controller.frames.get("AdvancedSettings").get_debug_color() if controller.frames.get("AdvancedSettings") else "#ff0f0f"

        # === Layout ===
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(outer)
        inner.grid(row=0, column=0)

        # === Top Button Row ===
        top_button_row = ctk.CTkFrame(inner)
        top_button_row.pack(fill="x", pady=(5, 0))
        ctk.CTkButton(top_button_row, text="Try Again", width=100, font=font, command=self.retry_last_response).pack(side="right", padx=10)
        self.edit_button = ctk.CTkButton(top_button_row, text="Edit Reply", width=100, font=font, command=self.toggle_edit_last_reply)
        self.edit_button.pack(side="right", padx=10)
        ctk.CTkButton(top_button_row, text="Back", width=100, font=font, command=self.confirm_back_to_main).pack(side="left", padx=10)

        # === Chat Display ===
        self.chat_display = ctk.CTkTextbox(inner, height=350, width=600, font=font, wrap="word",
                                           fg_color=entry_bg_color, text_color=text_color,
                                           border_color=accent_color, border_width=2)
        self.chat_display.pack(pady=10)
        self.chat_display.configure(state="disabled")
        self.chat_display.tag_config("thinking_tag", foreground="#AAAAAA")

        # === Entry Box ===
        self.entry = ctk.CTkTextbox(inner, width=500, height=120, font=font, wrap="word",
                                    fg_color=entry_bg_color, text_color=text_color,
                                    border_color=accent_color, border_width=2)
        self.entry.pack(pady=(0, 10))

        # === Text Tags ===
        self.chat_display.tag_config("user", foreground=self.user_color)
        self.chat_display.tag_config("bot", foreground=self.character_color)
        self.chat_display.tag_config("debug", foreground=self.debug_color)

        # === Button Row ===
        button_row = ctk.CTkFrame(inner)
        button_row.pack(pady=(0, 10))
        ctk.CTkButton(button_row, text="Send", width=100, font=font, command=self.send_message).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Save", width=100, font=font, command=self.save_session).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Load", width=100, font=font, command=self.prompt_and_load_session_folder).pack(side="left", padx=5)

        # === Memory Debug Toggle ===
        self.debug_toggle_var = ctk.BooleanVar(value=False)
        self.debug_toggle = ctk.CTkCheckBox(inner, text="Show memory debug", font=font,
                                            variable=self.debug_toggle_var, command=self.toggle_debug_mode)
        self.debug_toggle.pack(pady=(5, 10))

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
        if not self.llm_character or not self.session_name:
            messagebox.showerror("Missing Info", "Cannot save session without loaded character and session name.")
            return

        # Confirm with user
        confirm = messagebox.askyesno(
            "Confirm Save",
            "Warning: Saved bot posts cannot be retried after reloading.\n\nContinue with saving?"
        )
        if not confirm:
            return

        session_dir = os.path.join("Character", self.llm_character, "Sessions", self.session_name)
        os.makedirs(session_dir, exist_ok=True)

        # Save minimal chat.json
        chat_path = os.path.join(session_dir, "chat.json")
        chat_data = {
            "chat": self.chat_display.get("1.0", "end").strip(),
            "conversation_history": self.conversation_history
        }
        with open(chat_path, "w", encoding="utf-8") as f:
            json.dump(chat_data, f, indent=2)

        # Save full session_info.json
        info_path = os.path.join(session_dir, "session_info.json")
        info_data = {
            "llm_character": self.llm_character,
            "user_character": self.user_character,
            "session_name": self.session_name,
            "scenario_file": self.scenario_file,
            "prefix_file": self.prefix_file
        }
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info_data, f, indent=2)

        messagebox.showinfo("Session Saved", f"Session saved to:\n{chat_path}\nand\n{info_path}")

    def confirm_back_to_main(self):
        if messagebox.askyesno(
            "Return to Main Menu",
            "Are you sure you want to return to the main menu? Unsaved progress will be lost."
        ):
            self.reset_session_state()  # Clear old chat, characters, and memory
            self.controller.show_frame("StartMenu")

    def send_message(self):
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
        self.chat_display.insert("end", f"You: {user_input}\n\n", "user")
        self.chat_display.configure(state="disabled")

        if settings_data.get("auto_scroll", True):
            self.chat_display.see("end")

        self.conversation_history.append({"role": "user", "content": user_input})

        # Enforce max rolling memory size
        max_history = settings.get_chat_history_length()
        if max_history > 0 and len(self.conversation_history) > max_history * 2:
            self.conversation_history = self.conversation_history[-max_history * 2:]

        # Start background thread to fetch response
        threading.Thread(
            target=self.fetch_and_display_reply,
            args=(user_input, settings_data, self.scenario, self.prefix)
        ).start()

    def fetch_and_display_reply(self, user_message, settings_data, scenario_ui, prefix_ui):
        os.system("cls" if os.name == "nt" else "clear")
        self.last_prompt = user_message

        # Retrieve relevant memories
        memory_objects, memory_debug_lines = retrieve_relevant_memories(
            user_message,
            self.memory_index,
            self.memory_mapping,
            self.embedder,
            self.lemmatizer,
            settings_data,
            self.debug_mode
        )

        # Build prompt using new memory system
        prompt = self.conversation_service.build_prompt(
            user_message,
            memory_objects,
            self.scenario,
            self.prefix
        )

        payload = self.conversation_service.build_payload(prompt, settings_data)

        # Save for retry functionality
        self.last_built_prompt = prompt
        self.last_payload_used = payload
        self.memory_debug_lines = memory_debug_lines

        # Debug memory output
        print("\n=== RAW MEMORY OBJECTS ===")
        print(memory_objects)
        print("=========================\n")

        self.selected_memories = [m.get("memory_id", "???") for m in memory_objects]

        # Construct message list for LLM
        messages, filtered_history = self.conversation_service.build_chat_messages(
            self.conversation_history,
            self.scenario,
            self.prefix,
            memory_objects
        )
        payload["messages"] = messages

        # Inject character names into settings_data for debug visibility
        settings_data["llm_character"] = self.controller.active_session_data.get("llm_character", "(not set)")
        settings_data["user_character"] = self.controller.active_session_data.get("user_character", "(not set)")

        # Optional debug preview
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
                scenario_ui=self.scenario,
                prefix_ui=self.prefix
            )
            print(debug_text_console)

        # Launch LLM call in thread
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

        speaker_name = self.llm_character_config.get("name", "Bot")
        self.chat_display.insert("end", f"{speaker_name}: {clean_reply}\n\n", "bot")
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

    def load_session_assets(self, force_reload=False):
        session = getattr(self.controller, "active_session_data", None)
        if not session:
            print("[Error] No active session data.")
            return

        # Save session context to instance variables
        self.llm_character = session.get("llm_character", "")
        self.user_character = session.get("user_character", "")
        self.session_name = session.get("session_name", "")

        char_name = self.llm_character
        user_char = self.user_character
        session_folder = os.path.join("Character", char_name, "Sessions", self.session_name)

        if not char_name or not user_char:
            print("[Error] Missing character or user character in session data.")
            return

        # Load user character config and apply color
        user_path = os.path.join("Character", user_char, "character_config.json")
        if os.path.exists(user_path):
            with open(user_path, "r", encoding="utf-8") as f:
                self.user_character_config = json.load(f)
            user_color = self.user_character_config.get("text_color", "#00ccff")
            self.chat_display.tag_config("user", foreground=user_color)

        # Load and store LLM character config
        llm_path = os.path.join("Character", char_name, "character_config.json")
        if os.path.exists(llm_path):
            with open(llm_path, "r", encoding="utf-8") as f:
                self.llm_character_config = json.load(f)
        else:
            self.llm_character_config = {"name": "Bot"}

        path = os.path.join("Character", char_name)
        config_path = os.path.join(path, "character_config.json")
        index_path = os.path.join(path, "memory_index.faiss")
        mapping_path = os.path.join(path, "memory_mapping.json")

        if self.llm_character_config:
            self.character_color = self.llm_character_config.get("text_color", "#ffeb0f")
            self.chat_display.tag_config("bot", foreground=self.character_color)

            # Load scenario and prefix from selected files
            scenario_file = session.get("scenario_file")
            prefix_file = session.get("prefix_file")
            self.scenario_file = scenario_file or ""
            self.prefix_file = prefix_file or ""
            scenario_path = os.path.join("Character", char_name, "Scenarios", scenario_file) if scenario_file else None
            prefix_path = os.path.join("Character", char_name, "Prefix", prefix_file) if prefix_file else None

            try:
                if scenario_path and os.path.exists(scenario_path):
                    with open(scenario_path, "r", encoding="utf-8") as f:
                        self.scenario = f.read().strip()
                    print(f"[Session] Loaded scenario: {scenario_file}")

                if prefix_path and os.path.exists(prefix_path):
                    with open(prefix_path, "r", encoding="utf-8") as f:
                        self.prefix = f.read().strip()
                    print(f"[Session] Loaded prefix: {prefix_file}")
            except Exception as e:
                print(f"[Warning] Failed to load scenario or prefix: {e}")

        if os.path.exists(index_path) and os.path.exists(mapping_path):
            self.memory_index = faiss.read_index(index_path)
            with open(mapping_path, "r", encoding="utf-8") as f:
                self.memory_mapping = json.load(f)
        else:
            print("[Warning] Memory index or mapping file missing.")

        if not self.chat_display.get("1.0", "end").strip():
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"--- {char_name} loaded ---\nScenario: {self.scenario}\n\n")
            self.chat_display.configure(state="disabled")

        # Load chat history if chat.json exists
        chat_json_path = os.path.join(session_folder, "chat.json")
        if os.path.exists(chat_json_path):
            try:
                with open(chat_json_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.conversation_history = saved.get("conversation_history", [])
                print(f"[Session] Loaded chat history ({len(self.conversation_history)} messages).")
            except Exception as e:
                print(f"[Warning] Failed to load chat history: {e}")

        self.chat_initialized = True

    def render_conversation_to_display(self):
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")

        # Fallback label if user character is not defined
        session = getattr(self.controller, "active_session_data", {})
        user_label = session.get("user_character", "You")
        bot_label = session.get("llm_character", self.controller.selected_character)

        for entry in self.conversation_history:
            role = entry.get("role")
            content = entry.get("content", "")
            if role == "user":
                tag = "user"
                label = user_label
            else:
                tag = "bot"
                label = bot_label

            self.chat_display.insert("end", f"{label}: ", tag)
            self.chat_display.insert("end", content.strip() + "\n\n", tag)

        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")  # Auto-scroll to most recent message

    def reset_chat(self):
        self.chat_initialized = False
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self.entry.delete("1.0", "end")

        self.load_session_assets(force_reload=True)

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

    def reset_session_state(self):
        self.chat_initialized = False
        self.conversation_history.clear()
        self.scenario = ""
        self.prefix = ""
        self.last_prompt = None
        self.last_payload_used = None
        self.last_built_prompt = None
        self.selected_memories = []
        self.memory_debug_lines = []

        if hasattr(self, "chat_display"):
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", "end")
            self.chat_display.configure(state="disabled")

        if hasattr(self, "entry"):
            self.entry.delete("1.0", "end")

    def load_session(self, session_data):
        """Handles loading of new session data passed from Start Menu or manual folder load."""
        self.reset_session_state()

        char_name = session_data.get("llm_character", "")
        session_name = session_data.get("session_name", "")
        self.controller.selected_character = char_name
        session_folder = os.path.join("Character", char_name, "Sessions", session_name)

        # Auto-detect scenario and prefix if not provided
        if not session_data.get("scenario_file") or not session_data.get("prefix_file"):
            if os.path.exists(session_folder):
                try:
                    for file in os.listdir(session_folder):
                        file_lower = file.lower()
                        if not file_lower.endswith(".txt"):
                            continue
                        if not session_data.get("scenario_file") and file_lower.startswith("scenario"):
                            session_data["scenario_file"] = file
                        elif not session_data.get("prefix_file") and file_lower.startswith("prefix"):
                            session_data["prefix_file"] = file
                        if session_data.get("scenario_file") and session_data.get("prefix_file"):
                            break
                except Exception as e:
                    print(f"[Warning] Failed to auto-detect scenario/prefix in folder: {e}")

        # Store active session and load assets
        self.controller.active_session_data = session_data
        self.load_session_assets(force_reload=True)
        self.render_conversation_to_display()

    def prompt_and_load_session_folder(self):
        char_name = self.llm_character or self.controller.selected_character
        if not char_name:
            messagebox.showerror("Character Required", "No character selected. Please start a session first.")
            return

        sessions_path = os.path.join("Character", char_name, "Sessions")
        if not os.path.exists(sessions_path):
            messagebox.showerror("Not Found", f"No sessions folder found at:\n{sessions_path}")
            return

        session_folder = filedialog.askdirectory(
            initialdir=sessions_path,
            title="Select a Session Folder to Load"
        )
        if not session_folder:
            return  # Cancelled

        session_name = os.path.basename(session_folder)
        user_char = self.user_character or self.controller.active_session_data.get("user_character", "")

        session_data = {
            "llm_character": char_name,
            "user_character": user_char,
            "session_name": session_name,
            "scenario_file": "",
            "prefix_file": ""
        }

        self.load_session(session_data)