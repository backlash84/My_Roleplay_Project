# finalizer_panel.py

import os
import json
import faiss
import numpy as np
import customtkinter as ctk
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
from tkinter import messagebox

tokenizer = AutoTokenizer.from_pretrained("Intel/neural-chat-7b-v3-1")

DEFAULT_BASE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Character")
)

class FinalizerPanel(ctk.CTkFrame):
    def __init__(self, parent, character_name, character_path):
        super().__init__(parent)
        self.character_name = character_name
        self.character_path = character_path
        self.alias_rows = []

        # --- Title
        ctk.CTkLabel(self, text="Finalizer", font=("Arial", 20)).pack(pady=10)

        # --- Alias Section
        self.alias_container = ctk.CTkScrollableFrame(self, label_text="Aliases", height=200)
        self.alias_container.pack(fill="both", expand=False, padx=20, pady=(10, 0))
        self.load_alias_map()

        # --- Add/Run Buttons
        button_row = ctk.CTkFrame(self)
        button_row.pack(pady=20)

        ctk.CTkButton(button_row, text="Add Alias", command=self.add_alias_row).pack(side="left", padx=10)
        ctk.CTkButton(button_row, text="Run Finalizer", command=self.run_finalizer).pack(side="left", padx=10)

    def add_alias_row(self):
        row_frame = ctk.CTkFrame(self.alias_container)
        row_frame.pack(fill="x", pady=5)

        root_entry = ctk.CTkEntry(row_frame, placeholder_text="Root Tag", width=120)
        root_entry.grid(row=0, column=0, padx=5)

        alias_entry = ctk.CTkEntry(row_frame, placeholder_text="Alias List (comma-separated)", width=300)
        alias_entry.grid(row=0, column=1, padx=5)

        delete_button = ctk.CTkButton(row_frame, text="X", width=30, fg_color="red", command=lambda: self.remove_alias_row(row_frame))
        delete_button.grid(row=0, column=2, padx=5)

        self.alias_rows.append((row_frame, root_entry, alias_entry))

    def remove_alias_row(self, frame):
        for row in self.alias_rows:
            if row[0] == frame:
                self.alias_rows.remove(row)
                break
        frame.destroy()

    def get_alias_map(self):
        alias_map = {}
        for _, root_entry, alias_entry in self.alias_rows:
            root = root_entry.get().strip().lower()
            aliases = [a.strip().lower() for a in alias_entry.get().split(",") if a.strip()]
            if root and aliases:
                alias_map[root] = aliases
        return alias_map

    def run_finalizer(self):
        try:
            # Save aliases first
            alias_map = self.get_alias_map()
            alias_path = os.path.join(self.character_path, "alias_map.json")
            with open(alias_path, "w", encoding="utf-8") as f:
                json.dump(alias_map, f, indent=2)
            print(f"[INFO] Alias map saved to {alias_path}")

            # Run main finalization process
            base_path = os.path.dirname(self.character_path)
            finalize_memories(self.character_name, base_path)

            messagebox.showinfo("Success", f"Finalization complete for {self.character_name}.")
        except Exception as e:
            messagebox.showerror("Finalization Error", f"An error occurred:\n{str(e)}")

    def load_alias_map(self):
        alias_path = os.path.join(self.character_path, "alias_map.json")
        if not os.path.exists(alias_path):
            return

        try:
            with open(alias_path, "r", encoding="utf-8") as f:
                alias_map = json.load(f)

            for root, aliases in alias_map.items():
                row_frame = ctk.CTkFrame(self.alias_container)
                row_frame.pack(fill="x", pady=5)

                root_entry = ctk.CTkEntry(row_frame, width=120)
                root_entry.insert(0, root)
                root_entry.grid(row=0, column=0, padx=5)

                alias_entry = ctk.CTkEntry(row_frame, width=300)
                alias_entry.insert(0, ", ".join(aliases))
                alias_entry.grid(row=0, column=1, padx=5)

                delete_button = ctk.CTkButton(row_frame, text="X", width=30, fg_color="red", command=lambda f=row_frame: self.remove_alias_row(f))
                delete_button.grid(row=0, column=2, padx=5)

                self.alias_rows.append((row_frame, root_entry, alias_entry))

            print(f"[INFO] Loaded {len(alias_map)} aliases into panel")

        except Exception as e:
            print(f"[WARN] Could not load alias_map.json: {e}")

# Helper Functions 

def count_tokens(text):
    return len(tokenizer.encode(text, add_special_tokens=False))

def finalize_memories(character_name: str, base_path: str = DEFAULT_BASE_PATH):
    print(f"Starting finalization for character: {character_name}")

    memory_folder = os.path.join(base_path, character_name, "Personal_Memories")
    template_folder = os.path.join(base_path, character_name, "Memory_Templates")
    output_folder = os.path.join(base_path, character_name)
    os.makedirs(output_folder, exist_ok=True)

    model_name = "all-MiniLM-L6-v2-main"
    print("Loading embedding model...")
    model_path = os.path.join(os.path.dirname(__file__), model_name, model_name)
    model = SentenceTransformer(model_path)

    # Load templates
    templates = {}
    print("Loading templates...")
    for fname in os.listdir(template_folder):
        if fname.endswith(".json"):
            with open(os.path.join(template_folder, fname), "r", encoding="utf-8") as f:
                template = json.load(f)
                templates[template["template_name"]] = template
    print(f"Loaded {len(templates)} template(s)")

    # Load alias map if it exists
    alias_map_path = os.path.join(output_folder, "alias_map.json")
    alias_map = {}
    if os.path.exists(alias_map_path):
        try:
            with open(alias_map_path, "r", encoding="utf-8") as f:
                alias_map = json.load(f)
            print(f"[INFO] Loaded alias map with {len(alias_map)} entries")
        except Exception as e:
            print(f"[WARN] Failed to load alias map: {e}")

    # Setup FAISS index
    embedding_dim = model.get_sentence_embedding_dimension()
    index = faiss.IndexFlatIP(embedding_dim)
    memory_mapping = []

    print("Processing memories...")
    for folder_root, _, files in os.walk(memory_folder):
        for fname in files:
            if not fname.endswith(".json"):
                continue

            full_path = os.path.join(folder_root, fname)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            except Exception as e:
                print(f"[ERROR] Failed to open or parse: {full_path}")
                print(f"        Reason: {e}")
                continue

            template_name = memory.get("template_used", "").replace(".json", "").strip()
            print(f"  Found memory: {fname} | Template used: {template_name}")

            if template_name not in templates:
                print(f"  [SKIP] Template '{template_name}' not found for {fname}")
                continue

            template = templates[template_name]
            search_text, prompt_text = "", ""
            memory_id = memory.get("memory_id", fname.replace(".json", ""))
            tags = []
            importance = None

            for field in template["fields"]:
                label = field["label"]
                usage = field.get("usage", "Neither")
                value = memory.get(label, "")
                if label == "__perspective__":
                    print(f"[DEBUG] Perspective found: {value}")
                if isinstance(value, list):
                    value = ", ".join(value)
                elif isinstance(value, int):
                    value = str(value)

                if usage == "Search":
                    search_text += value + "\n"
                elif usage == "Prompt":
                    if label == "__perspective__":
                        print("[DEBUG] Injecting perspective into prompt.")
                        prompt_text += f"[PERSPECTIVE: {value}]\n"
                    else:
                        prompt_text += value + "\n"
                elif usage == "Both":
                    search_text += value + "\n"
                    if label == "__perspective__":
                        print("[DEBUG] Injecting perspective into prompt.")
                        prompt_text += f"[PERSPECTIVE: {value}]\n"
                    else:
                        prompt_text += value + "\n"

                if usage in ["Search", "Both"] and field["type"] == "tag":
                    tags.extend([t.strip() for t in memory.get(label, [])])
                if label == "__importance__":
                    importance = memory.get(label, "Medium")

            # === Append alias clarification note if a root tag is mentioned ===
            if alias_map:
                clarification_lines = []
                prompt_lower = prompt_text.lower()
                for root_tag, aliases in alias_map.items():
                    if root_tag.lower() in prompt_lower and aliases:
                        alias_list = ", ".join(aliases)
                        clarification_lines.append(f"{root_tag} also goes by the names {alias_list}.")

                if clarification_lines:
                    prompt_text += "\n\n" + "\n".join(clarification_lines)

            embedding = model.encode(search_text, convert_to_numpy=True, normalize_embeddings=True)
            index.add(np.array([embedding]))

            prompt_text = prompt_text.strip()
            token_count = count_tokens(prompt_text)
            llm_visible_text = prompt_text

            memory_mapping.append({
                "memory_id": memory_id,
                "prompt_text": llm_visible_text,
                "search_text": search_text.strip(),
                "tags": tags,
                "importance": importance,
                "token_count": token_count
            })

            print(f"  [OK] Processed: {memory_id} | Importance: {importance} | Tags: {tags}")

    print("\nSaving index and memory mapping...")
    faiss.write_index(index, os.path.join(output_folder, "memory_index.faiss"))
    with open(os.path.join(output_folder, "memory_mapping.json"), "w", encoding="utf-8") as f:
        json.dump(memory_mapping, f, indent=2, ensure_ascii=False)

    print(f"Finalization complete. Indexed {len(memory_mapping)} memory chunks.")
    total_tokens = sum(mem["token_count"] for mem in memory_mapping)
    print(f"Total LLM-visible token count across all memories: {total_tokens}")