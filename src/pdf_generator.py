"""
PDF Generator — converts a Document (text + image blocks from OCR or direct
extraction) into a clean, reflowed PDF using ReportLab.
"""
from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer

from .models import Document, ImageBlock, TextBlock

_PAGE_W, _PAGE_H = LETTER
_MARGIN = 1.0 * inch
_CONTENT_W = _PAGE_W - 2 * _MARGIN
# Pixels-to-points factor for 300 DPI source images
_PX_PER_PT_300 = 300.0 / 72.0


class PDFGenerator:
    def build(self, document: Document, output_path: str) -> None:
        pdf = SimpleDocTemplate(
            output_path,
            pagesize=LETTER,
            rightMargin=_MARGIN,
            leftMargin=_MARGIN,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
        )

        base = getSampleStyleSheet()

        normal_style = ParagraphStyle(
            'BookNormal',
            parent=base['Normal'],
            fontName='Times-Roman',
            fontSize=11,
            leading=15,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
        heading_style = ParagraphStyle(
            'BookHeading',
            parent=base['Heading1'],
            fontName='Times-Bold',
            fontSize=16,
            leading=22,
            spaceBefore=18,
            spaceAfter=8,
            alignment=TA_LEFT,
        )

        story = []

        for page in document.pages:
            for block in page.blocks:
                if isinstance(block, TextBlock):
                    text = block.text.strip()
                    if not text:
                        continue
                    # Escape XML reserved characters for ReportLab's markup parser
                    text = (text
                            .replace('&', '&amp;')
                            .replace('<', '&lt;')
                            .replace('>', '&gt;'))
                    story.append(Paragraph(text, heading_style if block.is_heading else normal_style))

                elif isinstance(block, ImageBlock):
                    if not Path(block.image_path).exists():
                        continue
                    pts_w, pts_h = _scale_to_fit(
                        block.original_size,
                        block.source_dpi,
                        _CONTENT_W,
                        _PAGE_H - 2 * _MARGIN - 0.5 * inch,
                    )
                    try:
                        story.append(RLImage(block.image_path, width=pts_w, height=pts_h))
                        story.append(Spacer(1, 0.15 * inch))
                    except Exception as exc:
                        print(f'  Warning: could not embed image: {exc}')

        pdf.build(story)


def _scale_to_fit(size_px, source_dpi, max_w_pts, max_h_pts):
    """Convert pixel dimensions to PDF points, scaled to fit within the given bounds."""
    px_per_pt = source_dpi / 72.0
    w_pts = size_px[0] / px_per_pt
    h_pts = size_px[1] / px_per_pt
    if w_pts > max_w_pts:
        h_pts *= max_w_pts / w_pts
        w_pts = max_w_pts
    if h_pts > max_h_pts:
        w_pts *= max_h_pts / h_pts
        h_pts = max_h_pts
    return w_pts, h_pts
