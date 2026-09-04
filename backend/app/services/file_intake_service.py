"""Extracts plain text from an uploaded workflow-intake file (design.md FR7
extended per user request: "upload a PDF/JPEG so AI can scan an existing
workflow"). Per docs/DECISIONS.md #4, no external AI/vision provider is
configured in this environment - there is no OCR engine available either -
so this only ever does deterministic, local text extraction:

- .txt/.md: read directly as text
- .pdf: pull the embedded text layer out with pypdf (works for
  text-based PDFs; scanned/image-only PDFs will yield no text)
- images (.jpg/.jpeg/.png/.gif/.bmp): cannot be parsed into text at all
  without OCR - these are accepted as a reference attachment only, and the
  caller is told so via is_image=True so the UI can be honest about it
  instead of pretending to auto-read a picture.
"""

import io

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}


class UnsupportedFileError(ValueError):
    pass


def _extension(filename):
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def extract_text_from_upload(filename, file_bytes):
    """Returns {"source_text": str, "is_image": bool, "note": str}."""
    ext = _extension(filename)

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        text = file_bytes.decode("utf-8", errors="replace")
        return {"source_text": text, "is_image": False, "note": None}

    if ext in SUPPORTED_PDF_EXTENSIONS:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise UnsupportedFileError(
                "PDF support isn't installed on the server (missing 'pypdf')."
            )
        reader = PdfReader(io.BytesIO(file_bytes))
        pages_text = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages_text).strip()
        note = None
        if not text:
            note = (
                "No text could be found in this PDF - it may be a scanned/image-only "
                "document. Add the steps manually below, or attach it for reference only."
            )
        return {"source_text": text, "is_image": False, "note": note}

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return {
            "source_text": "",
            "is_image": True,
            "note": (
                "Images can't be auto-read into steps in this environment (no OCR/vision "
                "AI is configured here). The file will be attached as a reference for "
                "whoever reviews this draft - please add the steps manually below."
            ),
        }

    raise UnsupportedFileError(
        "Unsupported file type '{}'. Upload a .txt, .md, .pdf, or an image (.jpg/.png/.gif/.bmp).".format(ext or "unknown")
    )
