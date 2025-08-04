"""
memory_utils.py

Provides vector-based memory retrieval using FAISS with keyword boosting.
Used to retrieve character memories relevant to the current user message by combining
semantic similarity with lemmatized tag overlap for fine-tuned selection.
"""
import re
import faiss
import numpy as np
import os
import json

def load_stopwords(file_path="config/Filtered_Words_List.txt") -> set:
    if not os.path.exists(file_path):
        print("[Warning] Stopwords file not found.")
        return set()

    with open(file_path, "r", encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}

def retrieve_relevant_memories(
    user_message,
    memory_index,
    memory_mapping,
    embedder,
    lemmatizer,
    settings_data,
    debug_mode=False
):
    top_k = settings_data.get("top_k", 5)
    similarity_threshold = settings_data.get("similarity_threshold", 0.7)
    boost_factor = settings_data.get("memory_boost", 0.5)

    try:
        top_k = int(top_k)
    except (ValueError, TypeError):
        top_k = 5

    if not memory_index or not memory_mapping:
        print("[Memory Retrieval] Index or mapping missing.")
        return "", []

    # Load stopwords (only once per call)
    stopwords = load_stopwords()

    character_path = settings_data.get("character_path", "")
    alias_map = load_alias_map(character_path)
    alias_lookup = {
        alias.lower(): root.lower()
        for root, aliases in alias_map.items()
        for alias in aliases
    }

    # === Step 1: Extract questions and emphasize them ===
    question_sentences = [s.strip() for s in re.split(r'(?<=[?!.])\s+', user_message) if s.strip().rstrip('"\'').endswith('?')]
    emphasized_input = " ".join(question_sentences + [user_message])
    query_embedding = embedder.encode([emphasized_input]).astype("float32")

    D, I = memory_index.search(query_embedding, top_k) 

    print("\n[DEBUG] FAISS Query Results")
    print ("Scores:", D[0]) 
    print("Indices:", I[0])
    print ("Mapping size:", len (memory_mapping))

    # === Step 2: Extract keywords with capitalized emphasis ===
    words = re.findall(r'\b\w+\b', user_message)
    cleaned_words = [w.strip(".,!?\"'").lower() for w in words]

    # Join words to search/replace multi-word aliases
    normalized_message = " ".join(cleaned_words)
    for alias_phrase, root in alias_lookup.items():
        pattern = r"\b" + re.escape(alias_phrase) + r"\b"
        normalized_message = re.sub(pattern, root.lower(), normalized_message)

    expanded_keywords = {
        lemmatizer.lemmatize(w)
        for w in normalized_message.split()
        if w not in stopwords
    }

    lemmatized_keywords = set()
    capitalized_flags = set()

    for w in words:
        base = lemmatizer.lemmatize(w.lower())
        if base in stopwords:
            continue  # skip stopwords entirely

        lemmatized_keywords.add(base)
        if w[0].isupper():
            lemmatized_keywords.add(base + "_CAP")
            capitalized_flags.add(base)

    results = []
    for dist, idx in zip(D[0], I[0]):
        print(f"\n[DEBUG] Checking index {idx} (score: {dist:.4f})")

        if idx >= len(memory_mapping):
            print("  [SKIP] Index out of range.")
            continue

        memory = memory_mapping[idx]
        summary = memory.get("prompt_text", "")
        tags = set()
        for t in memory.get("tags", []):
            t_low = t.lower()
            tags.add(alias_lookup.get(t_low, t_low))

        print(f"  Summary: {summary[:60]}...")
        print(f"  Tags: {tags}")

        lemmatized_tag_words = set()
        tag_to_words = {}
        for tag in tags:
            tag_words = re.findall(r'\b\w+\b', tag)
            tag_to_words[tag] = tag_words
            for word in tag_words:
                lemmatized_tag_words.add(lemmatizer.lemmatize(word))

        matched = set()
        for word in lemmatized_tag_words:
            if word in expanded_keywords or word + "_CAP" in expanded_keywords:
                matched.add(word)

        similarity = dist
        boost = boost_factor * len(matched)
        score = similarity + boost

        print(f"  Matched tag words: {matched}")
        print(f"  Similarity: {similarity:.4f}, Boost: {boost:.4f}, Final Score: {score:.4f}")
        print("   Passed threshold" if score >= similarity_threshold else " Rejected")

        if score >= similarity_threshold:
            results.append((score, memory, matched, dist, boost, tag_to_words))
            print("   Passed threshold")
        else:
            print("   Rejected: similarity below threshold")

    # === Construct alias clarification lines ONLY for mentioned root tags ===
    mentioned_clarifications = []
    for root_tag, aliases in alias_map.items():
        if root_tag.lower() in normalized_message:
            if aliases:
                mentioned_clarifications.append(
                    f"{root_tag} also goes by the names {', '.join(aliases)}."
                )

    results.sort(reverse=True, key=lambda x: x[0])
    selected = []
    debug_lines = []

    for score, memory, matched, dist, boost, tag_to_words in results[:top_k]:
        selected.append(memory)
        if debug_mode:
            debug_lines.append (f"Chunk: Score = {dist:.4f}, Boost = {boost:.2f}, Total = {score: 4f}")
            debug_lines.append(f" Base Score: {dist:.4f}")
            debug_lines.append(f"  Boost: {boost:.4f}")
            debug_lines.append(f"  Total: {score:.4f}")
            debug_lines.append(f"  Matched words: {', '.join(sorted(matched)) or '(none)'}")
            debug_lines.append("")

    # === Inject alias clarifications for roots actually mentioned in user input ===
    if selected and mentioned_clarifications:
        clarification_block = "\n\n" + "\n".join(mentioned_clarifications)
        selected[0]["prompt_text"] += clarification_block

        print("\n[DEBUG] Injected Alias Clarifications (only once):")
        for line in mentioned_clarifications:
            print(f"  - {line}")

    if debug_mode:
        debug_lines.insert(0, "_-- Raw FAISS Scores and Boosted Results ---")
        debug_lines.insert(0, f"Similarity Threshold: {similarity_threshold}")
        debug_lines.insert(0, f"Top K (Memory Chunks): {top_k}")
        debug_lines.insert(0, "\n=== Retrieved Memory Debug ===\n")
        debug_lines.append(f"Returned {len(selected)} memory chunk(s) after filtering.")
        debug_lines.append("=== End ===\n")

    return selected, debug_lines if debug_mode else []

def load_alias_map(character_path):
    alias_path = os.path.join(character_path, "alias_map.json")
    if not os.path.exists(alias_path):
        return {}
    try:
        with open(alias_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load alias map: {e}")
        return {}