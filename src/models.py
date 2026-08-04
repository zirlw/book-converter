from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class TextBlock:
    text: str
    is_heading: bool = False
    heading_level: int = 1  # 1 = chapter-level, 2 = section-level
    top_ratio: Optional[float] = None
    bottom_ratio: Optional[float] = None


@dataclass
class ImageBlock:
    # Path to a temp PNG file so large images are not kept in RAM
    image_path: str
    # Original pixel dimensions at source DPI
    original_size: Tuple[int, int]
    source_dpi: int = 300


@dataclass
class PageContent:
    page_num: int  # 1-indexed
    blocks: List = field(default_factory=list)


@dataclass
class Chapter:
    title: str
    page_num: int  # 1-indexed page number in the output PDF
    chapter_num: Optional[int] = None


@dataclass
class Document:
    pages: List[PageContent] = field(default_factory=list)
    _temp_files: List[str] = field(default_factory=list, repr=False)

    def add_temp_file(self, path: str) -> None:
        self._temp_files.append(path)

    def cleanup(self) -> None:
        """Delete all temporary image files created during OCR."""
        import os
        for path in self._temp_files:
            try:
                os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()
