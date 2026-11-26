from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from test_auth import context as context
from test_documents import account as account
from test_documents import upload

from app.core.exceptions import AppError
from app.services.document_preview import check_archive


def make_file(extension):
    output = BytesIO()
    if extension == "pdf":
        import pymupdf

        with pymupdf.open() as document:
            for number in range(2):
                page = document.new_page()
                page.insert_text((72, 72), f"PDF page {number + 1}")
            return document.tobytes()
    if extension == "docx":
        from docx import Document

        document = Document()
        document.add_paragraph("Word <script> text")
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Name"
        table.cell(0, 1).text = "Value"
        document.save(output)
    elif extension == "pptx":
        from pptx import Presentation
        from pptx.util import Inches

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = "PPT title"
        slide.placeholders[1].text = "Slide content"
        table = slide.shapes.add_table(1, 2, Inches(1), Inches(3), Inches(4), Inches(1)).table
        table.cell(0, 0).text = "PPT cell"
        presentation.save(output)
    elif extension == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active.title = "Data"
        workbook.active.append(["Name", "Value"])
        workbook.active.append(["Example", 123])
        workbook.create_sheet("Second").append(["Second sheet"])
        workbook.save(output)
        workbook.close()
    elif extension == "xls":
        import xlwt

        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("Legacy")
        sheet.write(0, 0, "Legacy XLS")
        sheet.write(1, 0, 123)
        workbook.save(output)
    return output.getvalue()


@pytest.mark.parametrize(
    "extension,kind,expected",
    [
        ("pdf", "pdf", None),
        ("docx", "word", "Word <script> text"),
        ("pptx", "presentation", "PPT title"),
        ("xlsx", "spreadsheet", "Example"),
        ("xls", "spreadsheet", "Legacy XLS"),
    ],
)
def test_preview_and_original_roundtrip(account, extension, kind, expected):
    client, headers = account
    raw = make_file(extension)
    document = upload(client, headers, "示例." + extension, raw)
    assert document["kind"] == kind and document["content"] == ""
    url = "/api/v1/documents/" + document["id"]
    assert client.get(url + "/download", headers=headers).content == raw
    restored = client.get(url, headers=headers).json()["data"]
    assert restored["preview"] == document["preview"]
    assert (
        client.get("/api/v1/documents", headers=headers, params={"kind": kind}).json()["data"][
            "total"
        ]
        == 1
    )
    if extension == "pdf":
        assert restored["preview"]["pages"] == 2
        for page in (1, 2):
            response = client.get(url + "/preview", headers=headers, params={"page": page})
            assert response.status_code == 200
            assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
            assert response.headers["cache-control"] == "no-store"
        assert client.get(url + "/preview?page=3", headers=headers).status_code == 422
    else:
        assert expected in str(restored["preview"]["sections"])
        assert client.get(url + "/preview", headers=headers).status_code == 422


def test_pdf_preview_requires_owner(account):
    from test_auth import bearer, login, registration

    client, headers = account
    document = upload(client, headers, "a.pdf", make_file("pdf"))
    url = "/api/v1/documents/" + document["id"] + "/preview"
    assert client.get(url).status_code == 401
    payload, _ = registration(client)
    assert client.get(url, headers=bearer(login(client, payload))).status_code == 404


def test_oversize_corrupt_legacy_and_encrypted(account):
    import pymupdf

    client, headers = account
    for filename, raw, status in [
        ("a.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), 413),
        ("a.xlsx", b"broken", 422),
        ("a.xls", b"broken", 422),
        ("a.ppt", b"legacy", 415),
        ("a.doc", b"legacy", 415),
    ]:
        assert (
            client.post(
                "/api/v1/documents", headers=headers, files={"file": (filename, raw)}
            ).status_code
            == status
        )
    with pymupdf.open() as document:
        document.new_page()
        raw = document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="test"
        )
    assert (
        client.post(
            "/api/v1/documents", headers=headers, files={"file": ("locked.pdf", raw)}
        ).status_code
        == 422
    )


def test_workbook_preview_limits_and_no_formula_execution(account):
    from openpyxl import Workbook

    client, headers = account
    workbook = Workbook()
    sheet = workbook.active
    sheet.cell(1, 1, "=1+1")
    sheet.cell(201, 31, "outside preview")
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    document = upload(client, headers, "limited.xlsx", output.getvalue())
    assert document["preview"]["truncated"] is True
    rows = document["preview"]["sections"][0]["rows"]
    assert len(rows) == 200 and len(rows[0]) == 30
    assert rows[0][0] == ""


def test_reject_xml_entities_and_macro_archives():
    for name, content in [
        ("word/document.xml", b'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///secret">]>'),
        ("xl/vbaProject.bin", b"code"),
    ]:
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr(name, content)
        with pytest.raises(AppError):
            check_archive(output.getvalue())


@pytest.mark.parametrize("extension", ["docx", "pptx"])
def test_wide_office_table_marks_truncation(account, extension):
    client, headers = account
    output = BytesIO()
    if extension == "docx":
        from docx import Document

        document = Document()
        document.add_table(rows=1, cols=31).cell(0, 30).text = "outside"
        document.save(output)
    else:
        from pptx import Presentation
        from pptx.util import Inches

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.shapes.add_table(1, 31, Inches(0), Inches(0), Inches(10), Inches(1)).table.cell(
            0, 30
        ).text = "outside"
        presentation.save(output)
    result = upload(client, headers, "wide." + extension, output.getvalue())
    assert result["preview"]["truncated"] is True
    assert "outside" not in str(result["preview"]["sections"])
