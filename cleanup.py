"""Post-processing for transcribed text: remove filler words, tidy spacing."""

import re

# Thai filler words/phrases (removed wherever they appear)
THAI_FILLERS = [
    "เอ่อ", "เอ้อ", "อ่า", "อืม", "อืมม", "เอิ่ม", "อะแบบ",
    "แบบว่า", "คือว่า", "ก็คือว่า", "อะไรอย่างงี้", "อะไรอย่างเงี้ย",
    "อะไรงี้", "อะไรเงี้ย", "ประมาณว่า", "ไรงี้",
]

# English fillers (matched as whole words, case-insensitive)
EN_FILLERS = [
    "um", "uh", "erm", "uhm", "hmm", "you know", "i mean", "like,",
]


def clean(text: str) -> str:
    t = text.strip()

    for f in THAI_FILLERS:
        t = t.replace(f, "")

    for f in EN_FILLERS:
        t = re.sub(rf"\b{re.escape(f)}\b[,]?\s*", "", t, flags=re.IGNORECASE)

    # collapse whitespace and space before punctuation
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,.!?])", r"\1", t)
    # collapse immediate duplicate words (stutter: "the the")
    t = re.sub(r"\b(\w+) \1\b", r"\1", t)

    return t.strip()
