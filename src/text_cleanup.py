"""Post-processing utilities to remove recurring header/footer/page-number text."""
import re
from collections import Counter
from typing import Set

from .models import Document, TextBlock

_MARGIN_TOP = 0.16
_MARGIN_BOTTOM = 0.84


def remove_recurring_marginalia(document: Document) -> int:
    total_pages = len(document.pages)
    if total_pages < 3:
        return 0

    min_repeats = max(3, int(total_pages * 0.2))
    counts: Counter = Counter()

    for page in document.pages:
        seen: Set[str] = set()
        for block in page.blocks:
            if not isinstance(block, TextBlock):
                continue
            if not _is_margin_block(block):
                continue
            norm = _normalize_margin_text(block.text)
            if norm:
                seen.add(norm)
        counts.update(seen)

    recurring = {text for text, cnt in counts.items() if cnt >= min_repeats}

    removed = 0
    for page in document.pages:
        kept = []
        for block in page.blocks:
            if not isinstance(block, TextBlock):
                kept.append(block)
                continue
            if not _is_margin_block(block):
                kept.append(block)
                continue

            text = block.text.strip()
            norm = _normalize_margin_text(text)
            if _is_page_number_like(text) or (norm and norm in recurring):
                removed += 1
                continue

            kept.append(block)
        page.blocks = kept

    return removed


def _is_margin_block(block: TextBlock) -> bool:
    if block.top_ratio is None or block.bottom_ratio is None:
        return False
    return block.top_ratio <= _MARGIN_TOP or block.bottom_ratio >= _MARGIN_BOTTOM


def _normalize_margin_text(text: str) -> str:
    text = text.strip().lower()
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[_\-]{2,}', '-', text)
    text = re.sub(r'\b\d+\b', '#', text)
    text = re.sub(r'\b[ivxlcdm]{1,8}\b', '#', text)
    text = text.strip(' -.:|')
    if len(text) < 3:
        return ''
    return text


def _is_page_number_like(text: str) -> bool:
    value = text.strip().lower()
    if not value:
        return False

    value = re.sub(r'^[\[(\-\s]+|[\])\-\s]+$', '', value)
    if re.fullmatch(r'\d{1,5}', value):
        return True
    if re.fullmatch(r'[ivxlcdm]{1,8}', value):
        return True
    if re.fullmatch(r'page\s+\d{1,5}', value):
        return True
    if re.fullmatch(r'page\s+[ivxlcdm]{1,8}', value):
        return True

    return False
