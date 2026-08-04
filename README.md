# Book Converter
This is a demo copilot project for converting a scanned PDF book into text.

## Setup

1. Install Python 3.10+.
2. Install the Tesseract OCR binary.
	- Windows: https://github.com/UB-Mannheim/tesseract/wiki
	- Make sure Tesseract is available on your PATH.
3. Install Python dependencies from this folder:

```bash
pip install -r requirements.txt
```

## Usage

Run from this project folder:

```bash
python main.py <input-pdf> --title "<book-title>"
```

Examples:

```bash
# OCR a scanned PDF, build converted PDF, then split into booklets
python main.py scanned_book.pdf --title "Pride and Prejudice"

# Use faster direct text extraction when the input already has a text layer
python main.py digital_book.pdf --title "My Book" --direct-extract

# Limit booklet size and set OCR language
python main.py book.pdf --title "War and Peace" --max-pages 60 --lang eng

# Skip conversion and regenerate booklets from an existing converted PDF
python main.py book.pdf --title "My Book" --skip-convert

# Use a custom chapters file
python main.py book.pdf --title "My Book" --skip-convert --chapters-json output/chapters.json
```

Outputs are written to the `output` directory by default, including:

- `output/converted.pdf`
- `output/chapters.json`
- `output/booklet_01.pdf`, `output/booklet_02.pdf`, etc.

## Troubleshooting

### 1) python or pip is not recognized

- Verify Python is installed:

```bash
python --version
```

- If `pip` is not recognized, use:

```bash
python -m pip install -r requirements.txt
```

- On Windows, if `python` opens the Microsoft Store, disable the App Execution Alias for Python in Windows Settings and reopen your terminal.

### 2) Tesseract is not installed or not on PATH

Symptoms:

- Runtime error that Tesseract cannot be found
- OCR mode fails but `--direct-extract` works

Fix:

1. Install Tesseract from the Windows build page: https://github.com/UB-Mannheim/tesseract/wiki
2. Add the install folder (for example, `C:\Program Files\Tesseract-OCR`) to PATH.
3. Open a new terminal and run:

```bash
tesseract --version
```

### 3) OCR quality is poor

- Increase render DPI:

```bash
python main.py book.pdf --title "My Book" --dpi 400
```

- Use the correct OCR language pack, for example:

```bash
python main.py book.pdf --title "My Book" --lang eng
```

- Ensure scans are straight and high contrast before conversion.

### 4) Chapters were not detected correctly

- The app writes detected chapter boundaries to `output/chapters.json`.
- Edit that file manually, then re-run using:

```bash
python main.py book.pdf --title "My Book" --skip-convert --chapters-json output/chapters.json
```

### 5) Memory or speed issues on very large books

- Process with `--direct-extract` if the PDF already contains text.
- Reduce OCR DPI (for example, 250-300) to lower memory usage.
- Run booklet generation separately after conversion using `--skip-convert`.