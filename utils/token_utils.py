from transformers import AutoTokenizer

# Initialize once and reuse
tokenizer = AutoTokenizer.from_pretrained("Intel/neural-chat-7b-v3-1", trust_remote_code=True)

def count_tokens(text: str) -> int:
    if not isinstance(text, str):
        return 0
    try:
        return len(tokenizer.encode(text.strip(), add_special_tokens=False))
    except Exception:
        return 0