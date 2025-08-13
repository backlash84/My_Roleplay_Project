# utils/text_utils.py
import re

# Split on question-mark sentence ends; tolerate spaces after '?'
_QSPLIT = re.compile(r'(?<=[?])(?:\s+|$)')

def extract_questions(text: str) -> list[str]:
    """
    Return a list of verbatim questions found in `text`.
    - Keeps only sentences that end with '?'
    - Strips surrounding quotes/spaces
    - De-duplicates while preserving order
    """
    if not isinstance(text, str) or not text.strip():
        return []
    pieces = [s for s in _QSPLIT.split(text) if '?' in s]
    out = []
    for s in pieces:
        s = s.strip()
        qpos = s.rfind('?')
        if qpos != -1:
            s = s[:qpos+1]
        s = s.strip().strip('"').strip("'").strip()
        if s.endswith('?'):
            out.append(s)
    seen = set()
    uniq = []
    for q in out:
        if q not in seen:
            uniq.append(q)
            seen.add(q)
    return uniq

def jaccard_like(a: str, b: str) -> float:
    """
    Lightweight overlap metric for anti-parroting checks.
    """
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union