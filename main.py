#!/usr/bin/env python3
"""
book-converter — Turn a scanned-PDF book into a clean text PDF, then slice it
into printable booklets with cover pages and tables of contents.

Steps performed
---------------
1. OCR  : render every page of the scanned PDF at high DPI, run Tesseract OCR,
          detect headings and non-text illustrations, write a converted PDF.
2. Split: detect chapter headings in the converted PDF, group whole chapters
          into booklets (≤ --max-pages each), prepend a cover + TOC to each.

Requirements
------------
  pip install PyMuPDF pytesseract Pillow reportlab numpy

  Tesseract OCR binary must also be installed:
    Windows : https://github.com/UB-Mannheim/tesseract/wiki
    macOS   : brew install tesseract
    Linux   : sudo apt install tesseract-ocr

Usage examples
--------------
  python main.py book.pdf --title "Pride and Prejudice"
  python main.py book.pdf --title "War and Peace" --max-pages 60 --lang eng
  python main.py book.pdf --title "My Book" --direct-extract
  python main.py book.pdf --title "My Book" --skip-convert
"""
import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Dependency check (runs before heavy imports so errors are readable)
# ---------------------------------------------------------------------------

def _check_dependencies() -> None:
    missing = []

    try:
        import fitz  # noqa: F401
    except ImportError:
        missing.append('PyMuPDF         →  pip install PyMuPDF')

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append('Pillow          →  pip install Pillow')

    try:
        from reportlab.platypus import SimpleDocTemplate  # noqa: F401
    except ImportError:
        missing.append('reportlab       →  pip install reportlab')

    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append('numpy           →  pip install numpy')

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except ImportError:
        missing.append('pytesseract     →  pip install pytesseract')
    except Exception:
        missing.append(
            'Tesseract OCR binary  →  https://github.com/UB-Mannheim/tesseract/wiki  '
            '(or brew install tesseract / apt install tesseract-ocr)'
        )

    if missing:
        print('Missing dependencies:')
        for item in missing:
            print(f'  {item}')
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Convert a scanned PDF book to text and create printable booklets.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('input_pdf', help='Path to the scanned input PDF')
    p.add_argument('--title', required=True,
                   help='Book title — printed on every booklet cover')
    p.add_argument('--output-dir', default='output',
                   help='Directory for output files  (default: output/)')
    p.add_argument('--max-pages', type=int, default=80,
                   help='Maximum content pages per booklet, excluding cover & TOC  '
                        '(default: 80)')
    p.add_argument('--lang', default='eng',
                   help='Tesseract language code(s), e.g. "eng" or "eng+fra"  '
                        '(default: eng)')
    p.add_argument('--dpi', type=int, default=300,
                   help='DPI used when rendering scanned pages for OCR  (default: 300)')
    p.add_argument('--direct-extract', action='store_true',
                   help='Skip OCR — extract text directly from a PDF that already '
                        'has a text layer (much faster)')
    p.add_argument('--skip-convert', action='store_true',
                   help='Skip both OCR and direct extraction; use an existing '
                        'converted PDF in --output-dir (or --converted-pdf)')
    p.add_argument('--converted-pdf',
                   help='Explicit path to an existing converted PDF '
                        '(only used with --skip-convert)')
    p.add_argument('--chapters-json',
                   help='Path to a chapters JSON file to use instead of auto-detection. '
                        'Format: [{"title": "...", "page_num": N}, ...]')
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _build_parser().parse_args()

    _check_dependencies()

    from src.chapter_detector import ChapterDetector
    from src.booklet_creator import BookletCreator
    from src.pdf_generator import PDFGenerator

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    converted_pdf = output_dir / 'converted.pdf'

    # -----------------------------------------------------------------------
    # Step 1 — produce the converted (text) PDF
    # -----------------------------------------------------------------------
    if args.skip_convert:
        if args.converted_pdf:
            converted_pdf = Path(args.converted_pdf)
        if not converted_pdf.exists():
            print(f'Error: converted PDF not found: {converted_pdf}')
            print('Run without --skip-convert to generate it.')
            sys.exit(1)
        print(f'Using existing converted PDF: {converted_pdf}')

    else:
        input_pdf = Path(args.input_pdf)
        if not input_pdf.exists():
            print(f'Error: input file not found: {args.input_pdf}')
            sys.exit(1)

        if args.direct_extract:
            from src.direct_extractor import DirectExtractor
            print(f'Step 1/3: Extracting text from \'{input_pdf.name}\'...')
            document = DirectExtractor().process(str(input_pdf))
        else:
            from src.ocr_processor import OCRProcessor
            print(f'Step 1/3: OCR processing \'{input_pdf.name}\' '
                  f'(lang={args.lang}, dpi={args.dpi})...')
            document = OCRProcessor(lang=args.lang, dpi=args.dpi).process(str(input_pdf))

        print(f'  Processed {len(document.pages)} pages')

        print('Step 2/3: Generating converted PDF...')
        PDFGenerator().build(document, str(converted_pdf))
        print(f'  Saved: {converted_pdf}')
        document.cleanup()

    # -----------------------------------------------------------------------
    # Step 2 — chapter detection
    # -----------------------------------------------------------------------
    if args.chapters_json:
        chapters_path = Path(args.chapters_json)
        if not chapters_path.exists():
            print(f'Error: chapters JSON not found: {args.chapters_json}')
            sys.exit(1)
        from src.models import Chapter
        raw = json.loads(chapters_path.read_text(encoding='utf-8'))
        chapters = [Chapter(title=c['title'], page_num=int(c['page_num']),
                            chapter_num=c.get('chapter_num')) for c in raw]
        print(f'Loaded {len(chapters)} chapters from {chapters_path.name}')
    else:
        if not args.skip_convert:
            print('Step 3/3: Detecting chapters and creating booklets...')
        else:
            print('Step 2/2: Detecting chapters and creating booklets...')
        chapters = ChapterDetector().detect_from_pdf(str(converted_pdf))

    if chapters:
        print(f'  Found {len(chapters)} chapter(s):')
        for ch in chapters[:12]:
            print(f'    p.{ch.page_num:>4}  {ch.title}')
        if len(chapters) > 12:
            print(f'    … and {len(chapters) - 12} more')
    else:
        print('  No chapter headings detected — booklets will be split by page count.')

    # Save chapter manifest so users can review / edit and re-run
    manifest = output_dir / 'chapters.json'
    manifest.write_text(
        json.dumps(
            [{'title': c.title, 'page_num': c.page_num, 'chapter_num': c.chapter_num}
             for c in chapters],
            indent=2,
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    print(f'  Chapter manifest: {manifest}')

    # -----------------------------------------------------------------------
    # Step 3 — booklet creation
    # -----------------------------------------------------------------------
    booklets = BookletCreator(title=args.title, max_pages=args.max_pages).create(
        str(converted_pdf), chapters, str(output_dir)
    )

    print(f'\nDone!  {len(booklets)} booklet(s) written to \'{output_dir}/\'')
    for b in booklets:
        print(f'  {Path(b).name}')


if __name__ == '__main__':
    main()
