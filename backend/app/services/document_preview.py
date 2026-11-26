"""Bounded, local-only previews. Never execute macros, formulas or external links."""

from io import BytesIO
from zipfile import BadZipFile, ZipFile

from app.core.exceptions import AppError

MAX_OFFICE_BYTES = 10 * 1024 * 1024


def invalid():
    return AppError(422, 42207, "File is damaged, encrypted or unsupported for preview")


def check_archive(raw: bytes):
    try:
        with ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 3000 or sum(item.file_size for item in entries) > 40 * 1024 * 1024:
                raise invalid()
            for item in entries:
                if item.flag_bits & 1 or "vbaproject" in item.filename.lower():
                    raise invalid()
                if item.file_size > 10 * 1024 * 1024:
                    raise invalid()
                if item.filename.lower().endswith((".xml", ".rels")):
                    xml = archive.read(item).upper()
                    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                        raise invalid()
    except (BadZipFile, RuntimeError, OSError, ValueError):
        raise invalid() from None


class PreviewBuilder:
    def __init__(self):
        self.remaining = 100000
        self.truncated = False
        self.sections = []

    def text(self, value):
        text = "" if value is None else str(value)
        limit = min(2000, self.remaining)
        if len(text) > limit:
            self.truncated = True
        text = text[:limit]
        self.remaining -= len(text)
        return text

    def section(self, title, paragraphs=None, rows=None):
        if self.remaining <= 0:
            self.truncated = True
            return
        self.sections.append(
            {
                "title": self.text(title),
                "paragraphs": [self.text(p) for p in (paragraphs or [])],
                "rows": [[self.text(cell) for cell in row] for row in (rows or [])],
            }
        )

    def result(self, pages=0):
        return {"sections": self.sections, "pages": pages, "truncated": self.truncated}


def pdf_document(raw):
    import pymupdf

    if not raw.startswith(b"%PDF-"):
        raise invalid()
    document = pymupdf.open(stream=raw, filetype="pdf")
    if document.needs_pass or not 1 <= document.page_count <= 300:
        document.close()
        raise invalid()
    return document


def extract_preview(extension: str, raw: bytes):
    builder = PreviewBuilder()
    try:
        if extension == "pdf":
            with pdf_document(raw) as document:
                return builder.result(document.page_count)
        if extension in ("docx", "pptx", "xlsx"):
            check_archive(raw)
        if extension == "docx":
            from docx import Document

            document = Document(BytesIO(raw))
            paragraphs = document.paragraphs
            builder.truncated = len(paragraphs) > 1000 or len(document.tables) > 30
            builder.section("正文", [p.text for p in paragraphs[:1000]])
            for number, table in enumerate(document.tables[:30], 1):
                rows = table.rows
                builder.truncated |= len(rows) > 200 or len(table.columns) > 30
                builder.section(
                    f"表格 {number}",
                    rows=[[cell.text for cell in list(row.cells)[:30]] for row in rows[:200]],
                )
        elif extension == "pptx":
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            presentation = Presentation(BytesIO(raw))
            builder.truncated = len(presentation.slides) > 100
            for index in range(min(len(presentation.slides), 100)):
                number, slide = index + 1, presentation.slides[index]
                texts, tables = [], []
                pending = list(slide.shapes)
                visited = 0
                while pending and visited < 1000:
                    shape = pending.pop(0)
                    visited += 1
                    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                        pending.extend(shape.shapes)
                    if shape.has_text_frame:
                        texts.append(shape.text)
                    if shape.has_table:
                        builder.truncated |= (
                            len(shape.table.rows) > 100 or len(shape.table.columns) > 30
                        )
                        tables.extend(
                            [
                                [cell.text for cell in list(row.cells)[:30]]
                                for row in list(shape.table.rows)[:100]
                            ]
                        )
                builder.truncated |= bool(pending) or len(tables) > 200
                builder.section(f"幻灯片 {number}", texts, tables[:200])
        elif extension == "xlsx":
            from openpyxl import load_workbook

            workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True, keep_links=False)
            try:
                builder.truncated = len(workbook.sheetnames) > 20
                for sheet in workbook.worksheets[:20]:
                    builder.truncated |= (sheet.max_row or 0) > 200 or (sheet.max_column or 0) > 30
                    rows = sheet.iter_rows(
                        min_row=1,
                        max_row=min(sheet.max_row or 1, 200),
                        min_col=1,
                        max_col=min(sheet.max_column or 1, 30),
                        values_only=True,
                    )
                    builder.section(sheet.title, rows=list(rows))
            finally:
                workbook.close()
        elif extension == "xls":
            import xlrd

            if not raw.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
                raise invalid()
            workbook = xlrd.open_workbook(file_contents=raw, on_demand=True)
            try:
                builder.truncated = workbook.nsheets > 20
                for index in range(min(workbook.nsheets, 20)):
                    sheet = workbook.sheet_by_index(index)
                    builder.truncated |= sheet.nrows > 200 or sheet.ncols > 30
                    rows = [
                        [sheet.cell_value(r, c) for c in range(min(sheet.ncols, 30))]
                        for r in range(min(sheet.nrows, 200))
                    ]
                    builder.section(sheet.name, rows=rows)
            finally:
                workbook.release_resources()
        else:
            raise invalid()
        return builder.result()
    except AppError:
        raise
    except Exception:
        # Do not leak document contents or parser internals in API errors.
        raise invalid() from None


def render_pdf_page(raw: bytes, page: int) -> bytes:
    import pymupdf

    try:
        with pdf_document(raw) as document:
            if page < 1 or page > document.page_count:
                raise AppError(422, 42207, "Invalid PDF page")
            sheet = document.load_page(page - 1)
            rect = sheet.rect
            if rect.width <= 0 or rect.height <= 0:
                raise invalid()
            scale = min(1.5, 1400 / max(rect.width, rect.height))
            return sheet.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")
    except AppError:
        raise
    except Exception:
        raise invalid() from None
