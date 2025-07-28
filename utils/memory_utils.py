"""
memory_utils.py

Provides vector-based memory retrieval using FAISS with keyword boosting.
Used to retrieve character memories relevant to the current user message by combining
semantic similarity with lemmatized tag overlap for fine-tuned selection.
"""
import re
import faiss
import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

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

    # === Step 1: Extract questions and emphasize them ===
    question_sentences = [s.strip() for s in re.split(r'(?<=[?!.])\s+', user_message) if s.strip().rstrip('"\'').endswith('?')]
    emphasized_input = " ".join(question_sentences + [user_message])
    query_embedding = embedder.encode([emphasized_input]).astype("float32")

    D, I = memory_index.search(query_embedding, top_k) 

    print("\n[DEBUG] FAISS Query Results")
    print ("Scores:", D[0]) print("Indices:", I[0])
    print ("Mapping size:", len (memory_mapping))

    # === Step 2: Extract keywords with capitalized emphasis ===
    words = re.findall(r'\b\w+\b', user_message)
    lemmatized_keywords = set()
    capitalized_flags = set()

    for w in words:
        base = lemmatizer.lemmatize(w.lower())
        lemmatized_keywords.add(base)
        if w[0].isupper():
            lemmatized_keywords.add(base + "_CAP")
            capitalized_flags.add(base)

    results = []
    for dist, idx in zip(D[0], I[0]):
        print(f"\n[DEBUG] Checking index (idx} (score: {dist:.4f})")

        if idx >= len(memory_mapping):
            print("  [SKIP] Index out of range.")
            continue

        memory = memory_mapping[idx]
        summary = memory.get("prompt_text", "")
        tags = set(t.lower() for t in memory.get("tags", []))

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
            if word in lemmatized_keywords or word + "_CAP" in lemmatized_keywords:
                matched.add(word)

        similarity = dist
        boost = boost_factor * len(matched)
        score = similarity + boost

        print(f"  Matched tag words: {matched}")
        print(f"  Similarity: {similarity:.4f}, Boost: {boost:.4f}, Final Score: {score:.4f}")
        print("   Passed threshold" if score >= similarity_threshold else " Rejected")

        if similarity >= similarity_threshold:
            results.append((score, memory, matched, dist, boost, tag_to_words))
            print("   Passed threshold")
        else:
            print("   Rejected: similarity below threshold")

    results.sort(reverse=True, key=lambda x: x[0])
    selected = []
    debug_lines = []

    for score, memory, matched, dist, boost, tag_to_words in results[:top_k]:
        selected.append(memory)
        if debug_mode:
            debug_lines.append (f"Chunk: Score = (dist:.4f}, Boost = {boost:.2f}, Total = (score: 4f)")
            debug_lines.append(f" Base Score: {dist:.4f)")
            debug_lines.append(f"  Boost: {boost:.4f}")
            debug_lines.append(f"  Total: {score:.4f}")
            debug_lines.append(f"  Matched words: {', '.join(sorted(matched)) or '(none)'}")
            debug_lines.append("")

    if debug_mode:
        debug_lines.insert(0, "_-- Raw FAISS Scores and Boosted Results ---")
        debug_lines.insert(0, f"Similarity Threshold: {similarity_threshold}")
        debug_lines.insert(0, f"Top K (Memory Chunks): {top_k}")
        debug_lines.insert(0, "\n=== Retrieved Memory Debug ===\n")
        debug_lines.append(f"Returned {len(selected)} memory chunk(s) after filtering.")
        debug_lines.append("=== End ===\n")

    return selected, debug_lines if debug_mode else []