import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_BASE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Character")
)


def finalize_memories(
    character_name: str, base_path: str = DEFAULT_BASE_PATH
):

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

    # Setup FAISS index
    embedding_dim = model.get_sentence_embedding_dimension()
    index = faiss.IndexFlatIP(embedding_dim)
    memory_mapping = []

    print("Processing memories...")
    for root, _, files in os.walk(memory_folder):
        for fname in files:
            if not fname.endswith(".json"):
                continue

            full_path = os.path.join(root, fname)
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

            embedding = model.encode(search_text, convert_to_numpy=True, normalize_embeddings=True)
            index.add(np.array([embedding]))

            memory_mapping.append({
                "memory_id": memory_id,
                "prompt_text": prompt_text.strip(),
                "search_text": search_text.strip(),
                "tags": tags,
                "importance": importance
            })

            print(f"  [OK] Processed: {memory_id} | Importance: {importance} | Tags: {tags}")

    print("\nSaving index and memory mapping...")
    faiss.write_index(index, os.path.join(output_folder, "memory_index.faiss"))
    with open(os.path.join(output_folder, "memory_mapping.json"), "w", encoding="utf-8") as f:
        json.dump(memory_mapping, f, indent=2, ensure_ascii=False)

    for i, mem in enumerate(memory_mapping):
        if "pizza" in mem.get("prompt_text", "").lower():
            print(f"Pizza memory found in mapping at index {i}")

    print(f"Finalization complete. Indexed {len(memory_mapping)} memory chunks.")