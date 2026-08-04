"""
Chapter Detector — scans the converted PDF's text layer for common chapter-heading
patterns and returns a list of Chapter objects with their page numbers.
"""
import re
from typing import List

import fitz

from .models import Chapter

# Patterns matched against the *start* of a stripped line
_PATTERNS = [
    re.compile(r'^(?:CHAPTER|Chapter|chapter)\s+(?:\d+|[IVXLCDM]+|[A-Z][a-z]+)\b'),
    re.compile(r'^(?:CHAPTER|Chapter|chapter)\b[\s\.:\-]*$'),
    re.compile(r'^(?:PART|Part|part)\s+(?:\d+|[IVXLCDM]+|[A-Z][a-z]+)\b'),
    re.compile(r'^[IVXLCDM]{1,6}\.\s'),  # e.g. "IV. The Storm"
    re.compile(r'^(?:BOOK|Book|book)\s+(?:\d+|[IVXLCDM]+|[A-Z][a-z]+)\b'),
]


class ChapterDetector:
    def detect_from_pdf(self, pdf_path: str) -> List[Chapter]:
        pdf = fitz.open(pdf_path)
        chapters: List[Chapter] = []
        chapter_num = 0

        for page_idx in range(len(pdf)):
            text = pdf[page_idx].get_text()
            if not text.strip():
                continue

            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            heading = _find_heading(lines[:12])  # only look near the top of the page
            if heading:
                chapter_num += 1
                chapters.append(Chapter(
                    title=_full_title(lines, heading),
                    page_num=page_idx + 1,
                    chapter_num=chapter_num,
                ))

        pdf.close()
        return chapters


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _find_heading(lines: List[str]) -> str:
    for i, line in enumerate(lines):
        for pat in _PATTERNS:
            if pat.match(line):
                if re.match(r'^(?:CHAPTER|Chapter|chapter)\b[\s\.:\-]*$', line) and i + 1 < len(lines):
                    nxt = lines[i + 1]
                    if 0 < len(nxt) < 90 and not any(p.match(nxt) for p in _PATTERNS):
                        return f'{line} {nxt}'.strip()
                return line
    return ''


def _full_title(lines: List[str], heading: str) -> str:
    try:
        idx = lines.index(heading)
    except ValueError:
        return heading
    # Combine with the next line if it looks like a subtitle
    if idx + 1 < len(lines):
        nxt = lines[idx + 1]
        if 0 < len(nxt) < 80 and not any(p.match(nxt) for p in _PATTERNS):
            return f'{heading}: {nxt}'
    return heading
