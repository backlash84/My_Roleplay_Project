import customtkinter as ctk
import os
import json
from tkinter import filedialog, messagebox

class TemplateMakerPanel(ctk.CTkFrame):
    def __init__(self, parent, character_path):
        super().__init__(parent)
        self.character_path = character_path
        self.template_folder = os.path.join(character_path, "Memory_Templates")
        os.makedirs(self.template_folder, exist_ok=True)

        self.section_rows = []  # to store dynamically added rows

        # === HEADER FIELDS ===
        ctk.CTkLabel(self, text="Template Maker", font=("Arial", 20)).pack(pady=10)

        form = ctk.CTkFrame(self)
        form.pack(pady=10)

        # Template Name
        ctk.CTkLabel(form, text="Template Name:").grid(row=0, column=0, padx=10, sticky="e")
        self.template_name_entry = ctk.CTkEntry(form, width=300)
        self.template_name_entry.grid(row=0, column=1, padx=10)

        # Created By
        ctk.CTkLabel(form, text="Created By:").grid(row=1, column=0, padx=10, sticky="e")
        self.created_by_entry = ctk.CTkEntry(form, width=300)
        self.created_by_entry.grid(row=1, column=1, padx=10)

        # Tags
        ctk.CTkLabel(form, text="Tags:").grid(row=2, column=0, padx=10, sticky="e")
        self.tags_entry = ctk.CTkEntry(form, width=300)
        self.tags_entry.grid(row=2, column=1, padx=10)

        # Default Perspective
        ctk.CTkLabel(form, text="Default Perspective:").grid(row=3, column=0, padx=10, sticky="e")
        self.perspective_var = ctk.StringVar(value="First Hand")
        self.perspective_dropdown = ctk.CTkOptionMenu(
            form,
            variable=self.perspective_var,
            values=["First Hand", "Second Hand", "Lore"]
        )
        self.perspective_dropdown.grid(row=3, column=1, padx=10)

        # === DYNAMIC SECTION AREA ===
        self.section_container = ctk.CTkScrollableFrame(self, label_text="Template Fields", height=300)
        self.section_container.pack(fill="both", expand=True, padx=20, pady=10)

        # === CONTROL BUTTONS ===
        button_row = ctk.CTkFrame(self)
        button_row.pack(pady=15)

        ctk.CTkButton(button_row, text="Add New Section", command=self.add_section).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Save", command=self.save_template).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Load", command=self.load_template).pack(side="left", padx=10)

    def add_section(self):
        row = TemplateRow(self.section_container, self.remove_section, self.move_section)
        self.section_rows.append(row)

    def remove_section(self, row):
        if row in self.section_rows:
            self.section_rows.remove(row)

    def save_template(self):
        name = self.template_name_entry.get().strip()
        if not name:
            messagebox.showerror("Missing Name", "Template must have a name.")
            return

        perspective_value = self.perspective_var.get()

        # === Hardcoded Required Fields ===
        hardcoded_fields = [
            {"label": "__template_name__", "type": "text", "usage": "Neither"},
            {"label": "__created_by__", "type": "text", "usage": "Neither"},
            {"label": "__tags__", "type": "tag", "usage": "Search"},
            {"label": "__importance__", "type": "dropdown", "usage": "Search", "options": ["Low", "Medium", "High"], "default_value": "Medium"},
            {"label": "__perspective__", "type": "dropdown", "usage": "Both",
             "options": ["First Hand", "Second Hand", "Lore"], "default_value": perspective_value},
        ]

        # === User-Defined Fields ===
        user_fields = [row.to_dict() for row in self.section_rows]

        # Avoid accidental duplication of mandatory labels
        protected_labels = {field["label"] for field in hardcoded_fields}
        filtered_user_fields = [field for field in user_fields if field["label"] not in protected_labels]

        data = {
            "template_name": name,
            "created_by": self.created_by_entry.get().strip(),
            "tags": [tag.strip() for tag in self.tags_entry.get().split(",") if tag.strip()],
            "fields": hardcoded_fields + filtered_user_fields
        }

        save_path = os.path.join(self.template_folder, f"{name}.json")

        if os.path.exists(save_path):
            confirm = messagebox.askyesno(
                "Overwrite Existing Template",
                f"A template named '{name}' already exists.\nDo you want to overwrite it?"
            )
            if not confirm:
                return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Saved", f"Template saved as {name}.json.")
        except Exception as e:
            messagebox.showerror("Save Failed", str(e))

    def load_template(self):
        path = filedialog.askopenfilename(
            title="Load Template",
            initialdir=self.template_folder,
            filetypes=[("JSON Files", "*.json")]
        )

        if not path:
            return  # User cancelled

        try:
            with open(path, "r", encoding="utf-8") as f:
                template = json.load(f)
        except Exception as e:
            messagebox.showerror("Load Failed", f"Could not load template:\n{e}")
            return

        # Fill top-level fields
        self.template_name_entry.delete(0, "end")
        self.template_name_entry.insert(0, template.get("template_name", ""))

        self.created_by_entry.delete(0, "end")
        self.created_by_entry.insert(0, template.get("created_by", ""))

        self.tags_entry.delete(0, "end")
        self.tags_entry.insert(0, ", ".join(template.get("tags", [])))

        # Set default perspective
        for field in template.get("fields", []):
            if field.get("label") == "__perspective__":
                default_val = field.get("default_value", "First Hand")
                if default_val in ["First Hand", "Second Hand", "Lore"]:
                    self.perspective_var.set(default_val)
                break

        # Clear current section rows
        for row in self.section_rows:
            row.frame.destroy()
        self.section_rows.clear()

        # Recreate each user-defined section
        for field in template.get("fields", []):
            label = field.get("label")
            if label in ["__template_name__", "__created_by__", "__tags__", "__importance__", "__perspective__"]:
                continue  # Skip mandatory fields — handled elsewhere

            row = TemplateRow(self.section_container, self.remove_section, self.move_section)

            row.label_entry.insert(0, label or "")
            row.type_var.set(field.get("type", "text"))
            row.type_dropdown.set(field.get("type", "text"))
            row.on_type_change(field.get("type", "text"))

            row.usage_var.set(field.get("usage", "Both"))
            row.usage_dropdown.set(field.get("usage", "Both"))

            default = field.get("default_value", "")
            if default:
                row.default_entry.insert(0, default)

            # Handle field-specific extras
            if row.options_entry:
                ftype = field.get("type")
                if ftype == "dropdown" and "options" in field:
                    row.options_entry.insert(0, ", ".join(field["options"]))
                elif ftype == "tag" and "suggested_tags" in field:
                    row.options_entry.insert(0, ", ".join(field["suggested_tags"]))
                elif ftype == "text" and "rows" in field:
                    row.options_entry.insert(0, str(field["rows"]))

            self.section_rows.append(row)

    def move_section(self, row, direction):
        index = self.section_rows.index(row)
        new_index = index + direction

        if 0 <= new_index < len(self.section_rows):
            # Swap in the list
            self.section_rows[index], self.section_rows[new_index] = (
                self.section_rows[new_index],
                self.section_rows[index]
            )

            # Repack all rows in order
            for r in self.section_rows:
                r.frame.pack_forget()
                r.frame.pack(fill="x", pady=5)

class TemplateRow:
    def __init__(self, parent, remove_callback, move_callback):
        self.frame = ctk.CTkFrame(parent)
        self.frame.pack(fill="x", pady=5)

        self.move_callback = move_callback
        self.remove_callback = remove_callback

        # === LINE 1: Section Name, Field Type, Default Value ===
        line1 = ctk.CTkFrame(self.frame)
        line1.pack(fill="x", padx=5)

        self.label_entry = ctk.CTkEntry(line1, placeholder_text="Section Name", width=150)
        self.label_entry.grid(row=0, column=0, padx=5, pady=2)

        self.type_var = ctk.StringVar(value="text")
        self.type_dropdown = ctk.CTkOptionMenu(line1, variable=self.type_var, values=["text", "tag", "dropdown", "int"])
        self.type_dropdown.grid(row=0, column=1, padx=5, pady=2)
        self.type_dropdown.configure(width=100)
        self.type_dropdown.configure(command=self.on_type_change)

        self.default_entry = ctk.CTkEntry(line1, placeholder_text="Default Value", width=200)
        self.default_entry.grid(row=0, column=2, padx=5, pady=2)

        # === LINE 2: Usage, Options/Tags, Delete ===
        line2 = ctk.CTkFrame(self.frame)
        line2.pack(fill="x", padx=5)

        self.usage_var = ctk.StringVar(value="Both")
        self.usage_dropdown = ctk.CTkOptionMenu(line2, variable=self.usage_var, values=["Prompt", "Search", "Both", "Neither"])
        self.usage_dropdown.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.usage_dropdown.configure(width=120)

        self.extra_entry_container = ctk.CTkFrame(line2, height=30)  # fixed height
        self.extra_entry_container.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        self.delete_button = ctk.CTkButton(line2, text="X", width=30, fg_color="red", hover_color="#aa0000", command=self.remove_self)
        self.delete_button.grid(row=0, column=2, padx=5, pady=2, sticky="e")

        self.up_button = ctk.CTkButton(line2, text="↑", width=30, command=self.move_up)
        self.up_button.grid(row=0, column=3, padx=2)

        self.down_button = ctk.CTkButton(line2, text="↓", width=30, command=self.move_down)
        self.down_button.grid(row=0, column=4, padx=2)

        # Initial options/tag field (if applicable)
        self.on_type_change(self.type_var.get())

    def on_type_change(self, new_type):
        for widget in self.extra_entry_container.winfo_children():
            widget.destroy()

        self.options_entry = None

        if new_type == "tag":
            self.options_entry = ctk.CTkEntry(self.extra_entry_container, placeholder_text="Suggested Tags (comma-separated)", width=300)
            self.options_entry.pack()
        elif new_type == "dropdown":
            self.options_entry = ctk.CTkEntry(self.extra_entry_container, placeholder_text="Dropdown Options (comma-separated)", width=300)
            self.options_entry.pack()
        elif new_type == "text":
            container = ctk.CTkFrame(self.extra_entry_container)
            container.pack()

            ctk.CTkLabel(container, text="Text Rows:").pack(side="left", padx=2)
            self.options_entry = ctk.CTkEntry(container, placeholder_text="e.g. 1, 3, 5", width=80)
            self.options_entry.pack(side="left")

    def remove_self(self):
        self.frame.destroy()
        self.remove_callback(self)

    def to_dict(self):
        result = {
            "label": self.label_entry.get().strip(),
            "type": self.type_var.get(),
            "usage": self.usage_var.get()
        }

        default_val = self.default_entry.get().strip()
        if default_val:
            result["default_value"] = default_val

        if self.options_entry:
            field_type = self.type_var.get()

            if field_type == "dropdown":
                raw = self.options_entry.get().strip()
                result["options"] = [opt.strip() for opt in raw.split(",") if opt.strip()]

            elif field_type == "tag":
                raw = self.options_entry.get().strip()
                result["suggested_tags"] = [tag.strip() for tag in raw.split(",") if tag.strip()]

            elif self.type_var.get() == "text" and self.options_entry:
                rows = self.options_entry.get().strip()
                if rows.isdigit():
                    result["rows"] = int(rows)

        return result 

    def move_up(self):
        self.move_callback(self, -1)

    def move_down(self):
        self.move_callback(self, 1)