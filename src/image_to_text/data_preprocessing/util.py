from typing import List, Tuple
from tempfile import SpooledTemporaryFile
from PIL.Image import Image
from pypdfium2 import PdfDocument, PdfPage


def plain_pdf_extraction(pdf_document: PdfDocument) -> [(int, str)]:
    pages = []
    for page_index, page_content in enumerate(pdf_document, 0):
        page_text: str = page_content.get_textpage().get_text_range()
        pages.append((page_index, page_text))
    return pages


def extract_text(pdf_file: SpooledTemporaryFile, language: str = "eng") \
        -> List[Tuple[int, str, str, Image]]:
    pdf_document = PdfDocument(pdf_file)
    extracted_pages = plain_pdf_extraction(pdf_document)
    extracted_content: List[Tuple[int, str, str, Image]] = []
    for page_index, page_text in extracted_pages:
        plain_extraction_text_length = len(page_text.split(" "))
        page_image = pdf_page_to_image(pdf_document.get_page(page_index))
        extracted_content.append((page_index, page_text, "", page_image))
    return extracted_content


def pdf_page_to_image(page: PdfPage) -> Image:
    bitmap = page.render(scale=2)  # sacle=2 to increase resolution
    return bitmap.to_pil()
