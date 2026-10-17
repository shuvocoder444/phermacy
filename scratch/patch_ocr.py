import re
with open("pos/ocr_service.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace length check 3 with 2
code = code.replace(
    "words = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', ocr_text).split() if len(w) >= 3]",
    "words = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', ocr_text).split() if len(w) >= 2]"
)

new_fuzzy = """        all_brands_lower = {b.lower(): b for b in all_brands if b}
        words = [w for w in re.sub(r'[^a-zA-Z0-9]', ' ', ocr_text).split() if len(w) >= 2]
        for w in words[:6]:
            w_lower = w.lower()
            matches_lower = difflib.get_close_matches(w_lower, list(all_brands_lower.keys()), n=2, cutoff=0.55)
            matches = [all_brands_lower[m] for m in matches_lower]"""

code = re.sub(
    r'words = \[w for w in re\.sub.*?for w in words\[:6\]:.*?matches = difflib\.get_close_matches.*?cutoff=0\.6\)',
    new_fuzzy,
    code,
    flags=re.DOTALL
)

with open("pos/ocr_service.py", "w", encoding="utf-8") as f:
    f.write(code)

