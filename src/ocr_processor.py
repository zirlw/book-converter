"""
OCR Processor — renders each page of a scanned PDF to a high-DPI image,
runs Tesseract OCR, groups words into paragraphs, detects heading text,
and identifies non-text visual regions (illustrations, figures).
"""
import tempfile
from typing import List

import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from .models import Document, ImageBlock, PageContent, TextBlock
from .text_cleanup import remove_recurring_marginalia


class OCRProcessor:
    # Minimum gap height (fraction of page) before checking for visual content
    _MIN_GAP_RATIO = 0.04
    # Pixel standard deviation threshold — below this a region is treated as blank paper
    _MIN_VISUAL_STD = 12
    # Mean pixel value above this is considered white / near-white paper
    _MAX_WHITE_MEAN = 235
    # Minimum OCR word confidence to include
    _MIN_CONFIDENCE = 20
    # Paragraph average word height must exceed median × this to be a heading
    _HEADING_RATIO = 1.6
    # Fewer than this many words on a page → treat whole page as an illustration
    _MIN_TEXT_WORDS = 5

    def __init__(self, lang: str = 'eng', dpi: int = 300) -> None:
        self.lang = lang
        self.dpi = dpi
        self._scale = dpi / 72.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def process(self, pdf_path: str) -> Document:
        document = Document()
        pdf = fitz.open(pdf_path)
        total = len(pdf)

        for idx in range(total):
            print(f'\r  OCR: page {idx + 1}/{total}   ', end='', flush=True)
            pix = pdf[idx].get_pixmap(matrix=fitz.Matrix(self._scale, self._scale))
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            document.pages.append(self._process_image(img, idx + 1, document))

        print()
        pdf.close()
        removed = remove_recurring_marginalia(document)
        if removed:
            print(f'  Removed {removed} recurring header/footer/page-number block(s).')
        return document

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _process_image(self, img: Image.Image, page_num: int, doc: Document) -> PageContent:
        page = PageContent(page_num=page_num)
        w, h = img.size
        img_gray = np.array(img.convert('L'))

        try:
            ocr = pytesseract.image_to_data(
                img,
                lang=self.lang,
                output_type=Output.DICT,
                config='--psm 3 --oem 1',
            )
        except Exception as exc:
            print(f'\n  Warning: OCR failed on page {page_num}: {exc}')
            page.blocks.append(_save_image(img, doc))
            return page

        words = [
            {
                'text':      ocr['text'][i].strip(),
                'left':      ocr['left'][i],
                'top':       ocr['top'][i],
                'width':     ocr['width'][i],
                'height':    ocr['height'][i],
                'block_num': ocr['block_num'][i],
                'par_num':   ocr['par_num'][i],
                'line_num':  ocr['line_num'][i],
            }
            for i in range(len(ocr['text']))
            if ocr['text'][i].strip() and int(ocr['conf'][i]) > self._MIN_CONFIDENCE
        ]

        if len(words) < self._MIN_TEXT_WORDS:
            page.blocks.append(_save_image(img, doc))
            return page

        median_h = float(np.median([wd['height'] for wd in words]))

        # Group words into paragraphs
        paras: dict = {}
        for wd in words:
            key = (wd['block_num'], wd['par_num'])
            if key not in paras:
                paras[key] = {'words': [], 'top': wd['top'], 'bottom': wd['top'] + wd['height'], 'heights': []}
            p = paras[key]
            p['words'].append(wd)
            p['top'] = min(p['top'], wd['top'])
            p['bottom'] = max(p['bottom'], wd['top'] + wd['height'])
            p['heights'].append(wd['height'])

        sorted_paras = sorted(paras.values(), key=lambda p: p['top'])

        last_bottom = 0
        for para in sorted_paras:
            top, bottom = para['top'], para['bottom']

            # Check vertical gap above this paragraph for visual content
            if top - last_bottom > h * self._MIN_GAP_RATIO:
                region = img_gray[max(0, last_bottom):min(h, top), :]
                if _is_visual(region):
                    page.blocks.append(_save_image(img.crop((0, last_bottom, w, top)), doc))

            # Assemble paragraph text (line-aware, with hyphen joining)
            lines: dict = {}
            for wd in para['words']:
                lines.setdefault(wd['line_num'], []).append(wd)
            line_texts = [
                ' '.join(wd['text'] for wd in sorted(lines[ln], key=lambda wd: wd['left']))
                for ln in sorted(lines)
            ]
            text = _join_hyphenated('\n'.join(line_texts))

            avg_h = float(np.mean(para['heights']))
            page.blocks.append(TextBlock(
                text=text,
                is_heading=avg_h > median_h * self._HEADING_RATIO,
                top_ratio=top / h,
                bottom_ratio=bottom / h,
            ))
            last_bottom = bottom

        # Check trailing gap
        if h - last_bottom > h * self._MIN_GAP_RATIO:
            region = img_gray[last_bottom:h, :]
            if _is_visual(region):
                page.blocks.append(_save_image(img.crop((0, last_bottom, w, h)), doc))

        return page


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _is_visual(region: np.ndarray) -> bool:
    return region.size > 0 and float(region.std()) > 12 and float(region.mean()) < 235


def _join_hyphenated(text: str) -> str:
    """Merge soft-hyphen line breaks (word- \\n word → word-)."""
    lines = text.split('\n')
    out: List[str] = []
    i = 0
    while i < len(lines):
        if lines[i].endswith('-') and i + 1 < len(lines):
            out.append(lines[i][:-1] + lines[i + 1])
            i += 2
        else:
            out.append(lines[i])
            i += 1
    return '\n'.join(out)


def _save_image(img: Image.Image, doc: Document) -> ImageBlock:
    tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(tmp.name, format='PNG')
    tmp.close()
    doc.add_temp_file(tmp.name)
    return ImageBlock(image_path=tmp.name, original_size=img.size)
