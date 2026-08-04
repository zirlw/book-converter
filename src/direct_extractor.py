"""
Direct Extractor — for PDFs that already carry a text layer (e.g. born-digital or
previously OCR'd).  Extracts text blocks and embedded images directly via PyMuPDF
without running Tesseract.
"""
import tempfile

import fitz
from PIL import Image

from .models import Document, ImageBlock, PageContent, TextBlock
from .text_cleanup import remove_recurring_marginalia


class DirectExtractor:
    def process(self, pdf_path: str) -> Document:
        document = Document()
        pdf = fitz.open(pdf_path)
        total = len(pdf)

        for idx in range(total):
            print(f'\r  Extracting: page {idx + 1}/{total}   ', end='', flush=True)
            document.pages.append(self._process_page(pdf[idx], idx + 1, document))

        print()
        pdf.close()
        removed = remove_recurring_marginalia(document)
        if removed:
            print(f'  Removed {removed} recurring header/footer/page-number block(s).')
        return document

    @staticmethod
    def _process_page(page: fitz.Page, page_num: int, doc: Document) -> PageContent:
        content = PageContent(page_num=page_num)
        page_height = max(1.0, page.rect.height)

        # get_text("blocks") → (x0,y0,x1,y1, text, block_no, block_type)
        # block_type: 0 = text, 1 = image
        for block in sorted(page.get_text('blocks'), key=lambda b: (b[1], b[0])):
            btype = block[6]
            if btype == 0:
                text = block[4].strip()
                if text:
                    content.blocks.append(TextBlock(
                        text=text,
                        top_ratio=block[1] / page_height,
                        bottom_ratio=block[3] / page_height,
                    ))
            elif btype == 1:
                # Extract the embedded image
                clip = fitz.Rect(block[:4])
                pix = page.get_pixmap(clip=clip, dpi=150)
                img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                img.save(tmp.name, format='PNG')
                tmp.close()
                doc.add_temp_file(tmp.name)
                content.blocks.append(ImageBlock(image_path=tmp.name, original_size=img.size, source_dpi=150))

        return content
