"""
Booklet Creator — splits the converted PDF into individual booklets, each
containing whole chapters only.  Prepends a cover page and a table of
contents page to every booklet.
"""
from pathlib import Path
from typing import List, Tuple

import fitz  # PyMuPDF

from .models import Chapter

# US Letter in PDF points
_W = 612
_H = 792


class BookletCreator:
    def __init__(self, title: str, max_pages: int = 80) -> None:
        self.title = title
        self.max_pages = max_pages

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def create(self, pdf_path: str, chapters: List[Chapter], output_dir: str) -> List[str]:
        src = fitz.open(pdf_path)
        total_pages = len(src)
        src.close()

        if not chapters:
            print('  No chapters found — creating one booklet to avoid mid-chapter splits.')
            return self._single_booklet_without_chapters(pdf_path, total_pages, output_dir)

        ranges = _chapter_ranges(chapters, total_pages)
        groups = self._group_into_booklets(ranges)

        paths: List[str] = []
        for n, group in enumerate(groups, 1):
            out_path = str(Path(output_dir) / f'booklet_{n:02d}.pdf')
            self._build_booklet(pdf_path, group, n, out_path)
            first = group[0]['chapter'].title
            last = group[-1]['chapter'].title
            label = first if first == last else f'{first} … {last}'
            print(f'  Booklet {n:02d}: {label}  →  {Path(out_path).name}')
            paths.append(out_path)

        return paths

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _group_into_booklets(self, ranges: List[dict]) -> List[List[dict]]:
        groups: List[List[dict]] = []
        current: List[dict] = []
        used = 0
        for r in ranges:
            if current and used + r['count'] > self.max_pages:
                groups.append(current)
                current, used = [], 0
            current.append(r)
            used += r['count']
        if current:
            groups.append(current)
        return groups

    def _build_booklet(self, src_pdf: str, group: List[dict], num: int, out_path: str) -> None:
        src = fitz.open(src_pdf)
        out = fitz.open()

        self._draw_cover(out, num, group)
        toc_page_count = self._draw_toc(out, num, group)

        for r in group:
            out.insert_pdf(src, from_page=r['start'] - 1, to_page=r['end'] - 1)

        # Number the content pages (cover and TOC pages have no number)
        front_matter = 1 + toc_page_count  # cover + however many TOC pages
        for i in range(front_matter, len(out)):
            _stamp_page_number(out[i], i - front_matter + 1)

        out.save(out_path)
        out.close()
        src.close()

    # -- Cover page --------------------------------------------------------

    def _draw_cover(self, doc: fitz.Document, num: int, group: List[dict]) -> None:
        page = doc.new_page(width=_W, height=_H)

        # Dark navy background
        page.draw_rect(fitz.Rect(0, 0, _W, _H), color=(0.07, 0.14, 0.33), fill=(0.07, 0.14, 0.33))
        # Gold accent bars
        page.draw_rect(fitz.Rect(0, 0, _W, 10), color=(0.88, 0.72, 0.18), fill=(0.88, 0.72, 0.18))
        page.draw_rect(fitz.Rect(0, _H - 10, _W, _H), color=(0.88, 0.72, 0.18), fill=(0.88, 0.72, 0.18))

        font_size = _fit_fontsize(self.title, max_w=460, max_h=200, start=36, minimum=14)
        page.insert_textbox(fitz.Rect(76, 210, 536, 430), self.title,
                            fontsize=font_size, fontname='tibo',
                            color=(1.0, 1.0, 1.0), align=1)

        page.insert_textbox(fitz.Rect(76, 448, 536, 492), f'Volume {num}',
                            fontsize=18, fontname='tiro',
                            color=(0.88, 0.84, 0.60), align=1)

        if group:
            first_title = group[0]['chapter'].title
            last_title  = group[-1]['chapter'].title
            subtitle = first_title if first_title == last_title else f'{first_title}  \u2013  {last_title}'
            # Truncate very long subtitles
            if len(subtitle) > 90:
                subtitle = subtitle[:87] + '\u2026'
            page.insert_textbox(fitz.Rect(90, 504, 522, 550), subtitle,
                                 fontsize=11, fontname='tiit',
                                 color=(0.75, 0.75, 0.75), align=1)

            chapter_lines = _chapter_lines_for_cover(group)
            chapter_text = 'Included Chapters\n\n' + '\n'.join(chapter_lines)
            for size in (11, 10, 9, 8):
                spare = page.insert_textbox(
                    fitz.Rect(84, 560, 528, 742),
                    chapter_text,
                    fontsize=size,
                    fontname='tiro',
                    color=(0.93, 0.93, 0.93),
                    align=0,
                )
                if spare >= 0:
                    break

    # -- TOC page(s) -------------------------------------------------------

    def _draw_toc(self, doc: fitz.Document, num: int, group: List[dict]) -> int:
        """
        Draw one or more TOC pages.  Returns the number of TOC pages added.
        Content starts at booklet page (1 cover + N toc + 1).
        """
        # We'll know how many TOC pages we need after we draw them.
        # Use a two-pass approach: estimate first, then draw.
        entries = self._toc_entries(group, content_start_offset=0)  # placeholder offset

        entries_per_page = 24  # conservative estimate at 28pt row spacing
        toc_page_count = max(1, -(-len(entries) // entries_per_page))  # ceiling division

        # Real content starts at: 1 (cover) + toc_page_count + 1
        content_start = 1 + toc_page_count + 1
        entries = self._toc_entries(group, content_start_offset=content_start)

        for page_idx in range(toc_page_count):
            page_entries = entries[page_idx * entries_per_page:(page_idx + 1) * entries_per_page]
            pg = doc.new_page(width=_W, height=_H)

            if page_idx == 0:
                pg.insert_textbox(fitz.Rect(66, 55, 546, 105), 'Contents',
                                  fontsize=22, fontname='tibo',
                                  color=(0.0, 0.0, 0.0), align=1)
                pg.draw_line(fitz.Point(66, 110), fitz.Point(546, 110),
                             color=(0.35, 0.35, 0.35), width=0.8)
                y_start = 130.0
            else:
                y_start = 60.0

            y = y_start
            for title, page_num in page_entries:
                _draw_toc_entry(pg, title, page_num, y)
                y += 28.0

        return toc_page_count

    @staticmethod
    def _toc_entries(group: List[dict], content_start_offset: int) -> List[Tuple[str, int]]:
        entries = []
        running = 0
        for r in group:
            entries.append((r['chapter'].title, content_start_offset + running))
            running += r['count']
        return entries

    # -- Fallback (no chapters) --------------------------------------------

    def _single_booklet_without_chapters(self, pdf_path: str, total: int, out_dir: str) -> List[str]:
        src = fitz.open(pdf_path)
        out = fitz.open()
        pseudo_group = [{
            'chapter': Chapter(title='Entire Book (chapter detection unavailable)', page_num=1),
            'start': 1,
            'end': total,
            'count': total,
        }]

        self._draw_cover(out, 1, pseudo_group)
        toc_page_count = self._draw_toc(out, 1, pseudo_group)
        out.insert_pdf(src, from_page=0, to_page=total - 1)

        front_matter = 1 + toc_page_count
        for i in range(front_matter, len(out)):
            _stamp_page_number(out[i], i - front_matter + 1)

        out_path = str(Path(out_dir) / 'booklet_01.pdf')
        out.save(out_path)
        out.close()
        src.close()
        return [out_path]


# ------------------------------------------------------------------
# Module-level drawing helpers
# ------------------------------------------------------------------

def _chapter_ranges(chapters: List[Chapter], total_pages: int) -> List[dict]:
    ranges = []
    for i, ch in enumerate(chapters):
        start = ch.page_num
        end = chapters[i + 1].page_num - 1 if i + 1 < len(chapters) else total_pages
        ranges.append({'chapter': ch, 'start': start, 'end': end, 'count': end - start + 1})
    return ranges


def _draw_toc_entry(page: fitz.Page, title: str, page_num: int, y: float) -> None:
    display = title if len(title) <= 68 else title[:65] + '\u2026'
    page.insert_textbox(fitz.Rect(66, y, 492, y + 22), display,
                        fontsize=11, fontname='tiro', color=(0, 0, 0), align=0)
    # Dotted leader line
    page.draw_line(fitz.Point(494, y + 14), fitz.Point(532, y + 14),
                   color=(0.65, 0.65, 0.65), width=0.6, dashes='[2 3] 0')
    page.insert_textbox(fitz.Rect(492, y, 546, y + 22), str(page_num),
                        fontsize=11, fontname='tiro', color=(0, 0, 0), align=2)


def _stamp_page_number(page: fitz.Page, number: int) -> None:
    page.insert_textbox(
        fitz.Rect(0, _H - 36, _W, _H - 18),
        str(number),
        fontsize=9,
        fontname='tiro',
        color=(0.4, 0.4, 0.4),
        align=1,
    )


def _chapter_lines_for_cover(group: List[dict]) -> List[str]:
    lines: List[str] = []
    for idx, item in enumerate(group, 1):
        title = item['chapter'].title.strip() or f'Chapter {idx}'
        if len(title) > 72:
            title = title[:69] + '\u2026'
        lines.append(f'{idx}. {title}')

    max_visible = 18
    if len(lines) > max_visible:
        hidden = len(lines) - max_visible
        lines = lines[:max_visible]
        lines.append(f'... and {hidden} more chapter(s)')
    return lines


def _fit_fontsize(text: str, max_w: int, max_h: int, start: int = 36, minimum: int = 12) -> int:
    """Estimate a font size that fits text in the given pixel area (rough heuristic)."""
    size = start
    while size > minimum:
        chars_per_line = max(1, max_w // int(size * 0.55))
        lines = max(1, -(-len(text) // chars_per_line))  # ceiling
        if lines * size * 1.25 <= max_h:
            break
        size -= 2
    return size
