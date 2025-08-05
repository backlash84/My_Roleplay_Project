import customtkinter as ctk
import os
import json
import re
import tkinter as tk
import copy
from tkinter import messagebox
from tkinter import filedialog

def truncate_label(text, max_len=20):
    return text if len(text) <= max_len else text[:max_len - 3] + "..."

class MemoryMakerPanel(ctk.CTkFrame):
    def __init__(self, parent, character_path):
        super().__init__(parent)
        self.last_saved_state = None
        self.character_path = character_path
        self.memory_folder_root = os.path.join(character_path, "Personal_Memories")
        self.loaded_memories = []
        self.active_memory = None
        self.editor_widgets = {}
        self.selected_button = None
        self.current_memory_folder = None
        self.current_folder_path = None

        # Load available templates
        self.template_dir = os.path.join(character_path, "Memory_Templates")
        self.available_templates = [f for f in os.listdir(self.template_dir) if f.endswith(".json")]

        # Load default template
        default_template_file = "Test Name.json"
        self.template_path = os.path.join(self.template_dir, default_template_file)
        with open(self.template_path, "r", encoding="utf-8") as f:
            self.template = json.load(f)

        top_controls = ctk.CTkFrame(self)
        top_controls.pack(pady=10)

        self.folder_label = ctk.CTkLabel(self, text="Folder: (Empty)", font=("Arial", 14))
        self.folder_label.pack(pady=(5, 0))

        ctk.CTkButton(top_controls, text="New Folder", command=self.create_new_memory_folder).pack(side="left", padx=5)
        ctk.CTkButton(top_controls, text="Load", command=self.load_memory_folder).pack(side="left", padx=5)
        ctk.CTkButton(top_controls, text="Delete", fg_color="red", command=self.delete_memory_folder).pack(side="left", padx=5)

        main_area = ctk.CTkFrame(self)
        main_area.pack(fill="both", expand=True, padx=10, pady=10)

        self.memory_list_frame = ctk.CTkFrame(main_area, width=200)
        self.memory_list_frame.pack(side="left", fill="y", padx=(0, 20))

        self.memory_scroll = ctk.CTkScrollableFrame(self.memory_list_frame, width=200, label_text="Memories")
        self.memory_scroll.pack(fill="both", expand=True, pady=(10, 5))

        # Far Right Panel
        self.new_memory_button = ctk.CTkButton(
            self.memory_scroll,
            text="New Memory",
            fg_color="orange",
            command=self.handle_new_memory_click
        )
        self.new_memory_button.pack(pady=5, anchor="w")

        self.editor_frame = ctk.CTkFrame(main_area, fg_color="grey")
        self.editor_frame.pack(side="left", fill="both", expand=True)

        self.template_dropdown = ctk.CTkOptionMenu(
            self.editor_frame,
            values=self.available_templates,
            command=self.change_template
        )
        self.template_dropdown.set(os.path.basename(self.template_path))
        self.template_dropdown.pack(pady=10)

        label_row = ctk.CTkFrame(self.editor_frame)
        label_row.pack(pady=(10, 5))

        ctk.CTkLabel(label_row, text="Memory ID:", font=("Arial", 14)).pack(side="left", padx=(0, 5))
        self.memory_id_entry = ctk.CTkEntry(label_row, width=200)
        self.memory_id_entry.insert(0, "No memory selected")
        self.memory_id_entry.pack(side="left")

        self.editor_container = ctk.CTkScrollableFrame(self.editor_frame)
        self.editor_container.pack(fill="both", expand=True, padx=10, pady=10)

        button_row = ctk.CTkFrame(self.editor_frame)
        button_row.pack(pady=(0, 15))
        ctk.CTkButton(button_row, text="Save", command=self.save_current_memory).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Reload", command=self.reload_editor_fields).pack(side="left", padx=5)

    def create_new_memory(self):
        new_memory = {}
        new_id = self.generate_new_memory_id()
        new_memory["memory_id"] = new_id
        self.memory_id_entry.delete(0, "end")
        self.memory_id_entry.insert(0, new_id)
        new_memory["template_used"] = self.template.get("template_name", "Default")

        # Set default tags from template-level tags list
        if "tags" in self.template:
            new_memory["Tags"] = self.template["tags"]

        for field in self.template["fields"]:
            label = field["label"]
            default = field.get("default_value", "")
            ftype = field["type"]

            if ftype == "tag":
                new_memory[label] = [tag.strip() for tag in default.split(",") if tag.strip()]
            elif ftype == "int":
                new_memory[label] = int(default) if default.isdigit() else 0
            elif ftype == "dropdown":
                new_memory[label] = field.get("default_value", "")
            else:
                new_memory[label] = default

        self.loaded_memories.append(new_memory)

        row_frame = ctk.CTkFrame(self.memory_scroll, fg_color="transparent")
        row_frame.pack(before=self.new_memory_button, pady=2, anchor="w")

        mem_button = ctk.CTkButton(row_frame, text=truncate_label(new_id), width=120)
        mem_button.configure(command=lambda m=new_memory, r=row_frame, b=mem_button: self.select_memory(m, r, b))
        mem_button.pack(side="left", padx=(0, 5))

        delete_button = ctk.CTkButton(
            row_frame, text="X", width=30,
            fg_color="red", hover_color="#aa0000",
            command=lambda: self.delete_memory(new_memory, row_frame)
        )
        delete_button.pack(side="left")

        new_memory["_row_frame"] = row_frame
        new_memory["_button"] = mem_button

        self.select_memory(new_memory, row_frame, mem_button)
        self.last_saved_state = self.snapshot_clean_memory(self.active_memory)
        self.after(100, lambda: self.memory_scroll._parent_canvas.yview_moveto(1.0))

    def delete_memory(self, memory, row_frame):
        memory_id = memory.get("memory_id")
        if not memory_id:
            return

        # Confirm before deletion
        confirm = messagebox.askyesno(
            "Delete Memory",
            f"Are you sure you want to permanently delete '{memory_id}'?"
        )
        if not confirm:
            return

        if memory.get("_button") == getattr(self, "selected_button", None):
            self.selected_button = None

        self.loaded_memories.remove(memory)
        row_frame.destroy()

        # Delete file from disk
        if self.current_folder_path:
            file_path = os.path.join(self.current_folder_path, f"{memory_id}.json")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"[DELETE] Removed file: {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete memory file:\n{e}")
            else:
                print(f"[DELETE] File not found: {file_path}")

        print(f"Deleted memory: {memory_id}")

    def select_memory(self, memory, row_frame, mem_button):
        if self.active_memory and self.has_unsaved_changes():
            result = messagebox.askyesno(
                "Unsaved Changes",
                f"'{self.active_memory['memory_id']}' has unsaved changes.\nSave before switching?"
            )
            if result:
                target_id = memory.get("memory_id")
                self.save_current_memory()
                # After saving, memory buttons are rebuilt. Refresh references.
                for mem in self.loaded_memories:
                    if mem.get("memory_id") == target_id:
                        memory = mem
                        row_frame = mem.get("_row_frame")
                        mem_button = mem.get("_button")
                        break

        # === Original selection logic resumes here ===
        self.active_memory = memory
        self.memory_id_entry.delete(0, "end")
        self.memory_id_entry.insert(0, memory["memory_id"])

        template_name = memory.get("template_used", "Default")
        template_path = os.path.join(self.template_dir, f"{template_name}.json")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                self.template = json.load(f)
            if hasattr(self, "template_dropdown"):
                self.template_dropdown.set(template_name)
        else:
            print(f"[TEMPLATE] Template '{template_name}' not found. Using current template in memory.")

        if self.selected_button:
            try:
                self.selected_button.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            except tk.TclError:
                self.selected_button = None

        self.selected_button = mem_button
        try:
            mem_button.configure(fg_color="#444444")
        except tk.TclError:
            pass

        self.build_editor_fields()

        # Ensure internal fields reflect widget values before snapshot
        self.update_active_memory_from_widgets()
        self.last_saved_state = self.snapshot_clean_memory(self.active_memory)

    def build_editor_fields(self):
        for widget in self.editor_container.winfo_children():
            widget.destroy()

        if self.active_memory is None:
            return  # Nothing to display

        self.editor_widgets = {}

        # === Default Template Metadata Fields ===
        ctk.CTkLabel(self.editor_container, text="Template Metadata", font=("Arial", 14, "bold")).pack(anchor="w", pady=(10, 5))

        # Created By
        ctk.CTkLabel(self.editor_container, text="Created By:").pack(anchor="w", pady=(5, 0))
        created_by_entry = ctk.CTkEntry(self.editor_container)
        created_by_entry.insert(
            0,
            self.active_memory.get(
                "__created_by__",
                self.active_memory.get("Created By", self.template.get("created_by", ""))
            ),
        )
        created_by_entry.pack(fill="x", pady=2)
        self.editor_widgets["__created_by__"] = (created_by_entry, "text")

        # Tags
        ctk.CTkLabel(self.editor_container, text="Tags:").pack(anchor="w", pady=(5, 0))
        tags_entry = ctk.CTkEntry(self.editor_container)
        tags_entry.insert(0, ", ".join(self.active_memory.get("Tags", [])))
        tags_entry.pack(fill="x", pady=2)
        self.editor_widgets["__tags__"] = (tags_entry, "tag")

        # Importance
        ctk.CTkLabel(self.editor_container, text="Importance:").pack(anchor="w", pady=(5, 0))
        importance_options = ["Low", "Medium", "High"]
        importance_dropdown = ctk.CTkOptionMenu(self.editor_container, values=importance_options)

        # Use saved memory value if available
        saved_importance = self.active_memory.get("Importance", "Medium")
        if saved_importance in importance_options:
            importance_dropdown.set(saved_importance)
        else:
            importance_dropdown.set("Medium")

        importance_dropdown.pack(fill="x", pady=2)
        self.editor_widgets["__importance__"] = (importance_dropdown, "dropdown")

        # Perspective
        ctk.CTkLabel(self.editor_container, text="Perspective:").pack(anchor="w", pady=(5, 0))
        perspective_options = ["First Hand", "Second Hand", "Lore"]
        perspective_dropdown = ctk.CTkOptionMenu(self.editor_container, values=perspective_options)

        saved_perspective = self.active_memory.get("__perspective__", "First Hand")
        if saved_perspective in perspective_options:
            perspective_dropdown.set(saved_perspective)
        else:
            perspective_dropdown.set("First Hand")

        perspective_dropdown.pack(fill="x", pady=2)
        self.editor_widgets["__perspective__"] = (perspective_dropdown, "dropdown")

        for field in self.template["fields"]:
            label = field["label"]
            if label in ["__template_name__", "__created_by__", "__tags__", "__importance__", "__perspective__"]:
                continue  # Prevent duplicate display of default metadata fields

            ftype = field["type"]

            ctk.CTkLabel(self.editor_container, text=label + ":").pack(anchor="w", pady=(5, 0))

            if ftype == "dropdown":
                options = field.get("options", [])
                widget = ctk.CTkOptionMenu(self.editor_container, values=options)

                # Pull the saved value
                saved_value = self.active_memory.get(label)
                if saved_value in options:
                    widget.set(saved_value)
                elif options:
                    widget.set(options[0])
                else:
                    widget.set("")

                self.editor_widgets[label] = (widget, "dropdown")

            elif ftype == "tag":
                widget = ctk.CTkEntry(self.editor_container)
                widget.insert(0, ", ".join(self.active_memory.get(label, [])))

                # Attach autocomplete if suggested_tags exist
                suggestions = field.get("suggested_tags", [])
                if suggestions:
                    self.attach_tag_autocomplete(widget, suggestions)

                self.editor_widgets[label] = (widget, "tag")
            elif ftype == "text":
                rows = field.get("rows", 1)
                if rows > 1:
                    widget = ctk.CTkTextbox(self.editor_container, height=rows * 24)
                    widget.insert("1.0", str(self.active_memory.get(label, "")))
                else:
                    widget = ctk.CTkEntry(self.editor_container)
                    widget.insert(0, str(self.active_memory.get(label, "")))

            elif ftype == "int":
                widget = ctk.CTkEntry(self.editor_container)
                widget.insert(0, str(self.active_memory.get(label, 0)))

            else:
                widget = ctk.CTkEntry(self.editor_container)
                widget.insert(0, str(self.active_memory.get(label, "")))

            widget.pack(fill="x", pady=2)
            self.editor_widgets[label] = (widget, ftype)

            # Scrolls to top of memory when opened. 
            self.editor_container._parent_canvas.yview_moveto(0.0)

    def save_current_memory(self):
        folder_path = getattr(self, "current_folder_path", None)
        if not folder_path:
            messagebox.showerror("No Folder", "No memory folder is currently selected.")
            return

        if self.active_memory is None:
            messagebox.showerror("No Memory", "No memory is currently selected.")
            return

        memory = self.active_memory

        folder_name = os.path.basename(folder_path)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[INFO] Created new folder: {folder_path}")

        # Ensure active memory reflects current widget values
        self.update_active_memory_from_widgets()
        memory["template_used"] = self.template.get("template_name", "Default")

        # Normalize built-in field labels for saving
        normalized_labels = {
            "__created_by__": "Created By",
            "__tags__": "Tags",
            "__importance__": "Importance",
        }

        # Prepare a copy for saving that excludes UI-only fields
        save_copy = {
            k: copy.deepcopy(v)
            for k, v in memory.items()
            if not (k.startswith("_") and not k.startswith("__"))
        }

        for src, dest in normalized_labels.items():
            if src in save_copy:
                save_copy[dest] = save_copy.pop(src)

        # === Rename Logic ===
        old_id = memory["memory_id"]
        new_id = self.memory_id_entry.get().strip()
        old_path = os.path.join(folder_path, f"{old_id}.json")
        new_path = os.path.join(folder_path, f"{new_id}.json")

        if new_id != old_id:
            # Check if new file already exists
            if os.path.exists(new_path):
                messagebox.showerror("Rename Failed", f"A memory named '{new_id}' already exists.")
                return

            # Rename file if needed
            if os.path.exists(old_path):
                os.rename(old_path, new_path)

            # Update memory and UI
            memory["memory_id"] = new_id
            save_copy["memory_id"] = new_id
            if "_button" in memory:
                try:
                    memory["_button"].configure(text=truncate_label(new_id))
                except tk.TclError:
                    pass

        # Final save path (now using possibly updated ID)
        final_path = os.path.join(folder_path, f"{memory['memory_id']}.json")

        # Overwrite check (only relevant if file pre-existed and wasn't renamed from self)
        if os.path.exists(final_path) and final_path != new_path:
            result = messagebox.askyesno(
                "Overwrite Memory?",
                f"A memory named '{memory['memory_id']}.json' already exists in folder '{folder_name}'.\n\nDo you want to overwrite it?"
            )
            if not result:
                return

        # Save file
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(save_copy, f, indent=2)

        messagebox.showinfo("Saved", f"Saved memory '{memory['memory_id']}' to '{folder_name}'.")

        saved_id = memory["memory_id"]
        self.load_memory_folder_from_path(folder_path)

        # Refresh active_memory reference to the reloaded object
        self.active_memory = None
        for mem in self.loaded_memories:
            if mem.get("memory_id") == saved_id:
                self.active_memory = mem
                btn = mem.get("_button")
                if btn:
                    try:
                        btn.configure(fg_color="#444444")
                        self.selected_button = btn
                    except tk.TclError:
                        self.selected_button = None
                break

        if self.active_memory:
            self.last_saved_state = self.snapshot_clean_memory(self.active_memory)
        else:
            self.last_saved_state = None

    def load_memory_folder(self):
        folder_path = filedialog.askdirectory(
            initialdir=self.memory_folder_root,
            title="Select Memory Folder"
        )
        if folder_path:
            self.load_memory_folder_from_path(folder_path)

    def load_memory_folder_from_path(self, folder_path):
        if not os.path.isdir(folder_path):
            return

        self.current_folder_path = folder_path
        folder_name = os.path.basename(folder_path)

        folder_name = os.path.basename(folder_path)
        self.folder_label.configure(text=f"Folder: {folder_name}")
        
        self.new_memory_button.configure(state="normal")

        self.loaded_memories.clear()
        self.selected_button = None

        # Destroy all widgets in scroll area
        for widget in self.memory_scroll.winfo_children():
            widget.destroy()

        # Load .json files
        def extract_number(name):
            match = re.search(r'(\d+)', name)
            return int(match.group(1)) if match else float('inf')

        for file in sorted(os.listdir(folder_path), key=extract_number):
            if file.endswith(".json"):
                full_path = os.path.join(folder_path, file)
                with open(full_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                    self.loaded_memories.append(memory)
                    self.create_memory_row(memory)

        # Recreate New Memory button
        self.new_memory_button = ctk.CTkButton(
            self.memory_scroll,
            text="New Memory",
            fg_color="orange",
            command=self.create_new_memory
        )
        self.new_memory_button.pack(pady=5, anchor="w")
        self.new_memory_button.configure(fg_color="orange")
        print(f"[LOAD] Loaded {len(self.loaded_memories)} memories from '{folder_name}'.")

    def reload_editor_fields(self):
        self.build_editor_fields()
        if self.active_memory:
            self.last_saved_state = self.snapshot_clean_memory(self.active_memory)

    def generate_new_memory_id(self):
        base_name = "Memory"
        existing_ids = [m["memory_id"] for m in self.loaded_memories]
        base_counts = {}

        # Extract base name and numeric suffix from all memory IDs
        for mem_id in existing_ids:
            match = re.match(r"^(.*?)(?: (\d+))?$", mem_id)
            if match:
                name = match.group(1).strip()
                num = int(match.group(2)) if match.group(2) else 1
                base_counts[name] = max(base_counts.get(name, 0), num)

        # Use the most recent base name as default if one exists
        if base_counts:
            most_recent_base = sorted(base_counts.items(), key=lambda x: x[1], reverse=True)[0][0]
            count = base_counts[most_recent_base] + 1
            return f"{most_recent_base} {count}"
        else:
            return base_name

    def change_template(self, template_filename):
        path = os.path.join(self.template_dir, template_filename)
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Template not found: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            self.template = json.load(f)

        self.template_path = path

        # Ask if we should apply the new template's defaults
        if self.active_memory is not None:
            result = messagebox.askyesno(
                "Change Template",
                "Switching templates will reset all fields to that template's default values.\nContinue?"
            )
            if not result:
                return

            # Apply the new template to the memory
            self.active_memory["template_used"] = self.template.get("template_name", "Default")

            # Reset the top-level Tags field if template provides defaults
            if "tags" in self.template:
                self.active_memory["Tags"] = self.template["tags"]
            else:
                self.active_memory["Tags"] = []

            for field in self.template.get("fields", []):
                label = field["label"]
                default = field.get("default_value", "")
                ftype = field["type"]

                if ftype == "tag":
                    self.active_memory[label] = [tag.strip() for tag in default.split(",") if tag.strip()]
                elif ftype == "int":
                    self.active_memory[label] = int(default) if default.isdigit() else 0
                elif ftype == "dropdown":
                    options = field.get("options", [])
                    self.active_memory[label] = default if default in options else (options[0] if options else "")
                else:
                    self.active_memory[label] = default

            # Also update memory_id field visually
            self.memory_id_entry.delete(0, "end")
            self.memory_id_entry.insert(0, self.active_memory["memory_id"])

            # Refresh editor with new defaults
            self.reload_editor_fields()

            # Snapshot clean state
            self.last_saved_state = self.snapshot_clean_memory(self.active_memory)

            # Reapply visual highlight to selected button
            if self.selected_button:
                try:
                    self.selected_button.configure(fg_color="#444444")
                except tk.TclError:
                    self.selected_button = None

    def get_memory_path(self, memory):
        memory_id = memory.get("memory_id", "Unnamed")
        filename = f"{memory_id}.json"
        return os.path.join(self.memory_folder_root, filename)

    def create_memory_row(self, memory):
        row_frame = ctk.CTkFrame(self.memory_scroll, fg_color="transparent")
        row_frame.pack(pady=2, anchor="w")  # <-- removed 'before=self.new_memory_button'

        mem_button = ctk.CTkButton(row_frame, text=truncate_label(memory["memory_id"]), width=120)
        mem_button.configure(command=lambda m=memory, r=row_frame, b=mem_button: self.select_memory(m, r, b))
        mem_button.pack(side="left", padx=(0, 5))

        delete_button = ctk.CTkButton(
            row_frame, text="X", width=30,
            fg_color="red", hover_color="#aa0000",
            command=lambda: self.delete_memory(memory, row_frame)
        )
        delete_button.pack(side="left")

        memory["_row_frame"] = row_frame
        memory["_button"] = mem_button

    def has_unsaved_changes(self):
        if self.active_memory is None:
            return False
        if self.last_saved_state is None:
            return True

        self.update_active_memory_from_widgets()

        current_clean = self.snapshot_clean_memory(self.active_memory)
        last_clean = self.last_saved_state

        return current_clean != last_clean

    def create_new_memory_folder(self):
        folder_name = ctk.CTkInputDialog(text="Enter new memory folder name:", title="New Folder").get_input()
        if not folder_name:
            return

        new_path = os.path.join(self.memory_folder_root, folder_name)
        if os.path.exists(new_path):
            messagebox.showerror("Folder Exists", f"A folder named '{folder_name}' already exists.")
            return

        os.makedirs(new_path)
        messagebox.showinfo("Created", f"Created new folder '{folder_name}'.")
        self.load_memory_folder_from_path(new_path)
        self.new_memory_button.configure(state="normal")
        self.new_memory_button.configure(fg_color="orange")
        self.folder_label.configure(text=f"Folder: {folder_name}")

    def snapshot_clean_memory(self, memory):
        clean = {}
        for k, v in memory.items():
            if k.startswith("_") and not k.startswith("__"):
                continue  # Skip UI-only fields
            if isinstance(v, list):
                clean[k] = [str(x).strip() for x in v]
            elif isinstance(v, int):
                clean[k] = int(v)
            else:
                clean[k] = str(v).strip()
        return clean

    def update_active_memory_from_widgets(self):
        if self.active_memory is None:
            return

        for label, (widget, ftype) in self.editor_widgets.items():
            if ftype == "tag":
                val = widget.get().strip()
                self.active_memory[label] = [v.strip() for v in val.split(",") if v.strip()]
            elif ftype == "int":
                val = widget.get().strip()
                self.active_memory[label] = int(val) if val.isdigit() else 0
            elif ftype == "text" and isinstance(widget, ctk.CTkTextbox):
                val = widget.get("1.0", "end").strip()
                self.active_memory[label] = val
            else:
                val = widget.get().strip()
                self.active_memory[label] = val

            # Keep human-readable duplicates in sync
            if label == "__created_by__":
                self.active_memory["Created By"] = self.active_memory[label]
            elif label == "__tags__":
                self.active_memory["Tags"] = self.active_memory[label]
            elif label == "__importance__":
                self.active_memory["Importance"] = self.active_memory[label]

    def handle_new_memory_click(self):
        if not self.current_folder_path:
            messagebox.showwarning("No Folder Selected", "Create or select a folder before creating memories.")
            return

        self.create_new_memory()

    def delete_memory_folder(self):
        if not self.current_folder_path:
            messagebox.showwarning("No Folder", "No memory folder is currently selected.")
            return

        folder_name = os.path.basename(self.current_folder_path)
        confirm = messagebox.askyesno(
            "Delete Folder",
            f"Are you sure you want to delete the folder '{folder_name}' and all its memories?\n\nThis cannot be undone."
        )

        if not confirm:
            return

        try:
            import shutil
            shutil.rmtree(self.current_folder_path)
            messagebox.showinfo("Deleted", f"Folder '{folder_name}' has been deleted.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete folder:\n{e}")
            return

        # Reset panel state
        self.current_folder_path = None
        self.loaded_memories.clear()
        self.active_memory = None
        self.selected_button = None

        for widget in self.memory_scroll.winfo_children():
            if widget is not self.new_memory_button:
                widget.destroy()

        self.editor_container._parent_canvas.yview_moveto(0.0)
        self.memory_id_entry.delete(0, "end")
        self.new_memory_button.configure(fg_color="#444444")
        self.folder_label.configure(text="Folder: (Empty)")

    def attach_tag_autocomplete(self, entry_widget, suggestions):
        listbox = None

        def close_listbox():
            nonlocal listbox
            if listbox:
                listbox.destroy()
                listbox = None

        def select_item(event=None):
            nonlocal listbox
            if not listbox:
                return

            try:
                selected = listbox.get(listbox.curselection())
            except tk.TclError:
                return

            # Replace last partial tag
            full_text = entry_widget.get()
            parts = [p.strip() for p in full_text.split(",")]
            parts[-1] = selected

            entry_widget.delete(0, "end")
            entry_widget.insert(0, ", ".join(parts))
            close_listbox()

        def on_key(event):
            nonlocal listbox

            if event.keysym in ["Up", "Down", "Return", "Escape"]:
                if not listbox:
                    return
                if event.keysym == "Return":
                    select_item()
                elif event.keysym == "Escape":
                    close_listbox()
                elif event.keysym == "Down":
                    current = listbox.curselection()
                    index = current[0] + 1 if current else 0
                    if index < listbox.size():
                        listbox.select_clear(0, "end")
                        listbox.select_set(index)
                        listbox.activate(index)
                elif event.keysym == "Up":
                    current = listbox.curselection()
                    index = current[0] - 1 if current else listbox.size() - 1
                    if index >= 0:
                        listbox.select_clear(0, "end")
                        listbox.select_set(index)
                        listbox.activate(index)
                return

            # Handle regular character typing
            full_text = entry_widget.get()
            parts = [p.strip() for p in full_text.split(",")]
            current = parts[-1] if parts else ""

            matches = [s for s in suggestions if s.lower().startswith(current.lower()) and s not in parts]
            close_listbox()
            if not matches or not current:
                return

            listbox = tk.Listbox(entry_widget.master, height=min(len(matches), 5), bg="#222", fg="white", highlightthickness=0, relief="flat")
            for match in matches:
                listbox.insert("end", match)

            # Position below the entry
            x = entry_widget.winfo_x()
            y = entry_widget.winfo_y() + entry_widget.winfo_height()
            listbox.place(x=x, y=y)

            listbox.select_set(0)
            listbox.activate(0)

            listbox.bind("<ButtonRelease-1>", select_item)

        entry_widget.bind("<KeyRelease>", on_key)

   