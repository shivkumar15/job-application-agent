from io import BytesIO

from reportlab.pdfgen import canvas

from app.resume_parser import analyze_resume


def make_pdf(text: str) -> BytesIO:
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    y = 800
    for line in text.splitlines():
        pdf.drawString(40, y, line[:110])
        y -= 18
    pdf.save()
    stream.seek(0)
    return stream


def test_extracts_basic_profile_fields():
    sample = """Alex Kumar
alex@example.com
+91 9876543210
Education
B.Tech Computer Science Current CGPA: 8.2
Technical Skills
Python, React, React.js, Node.js, MongoDB
Work Experience
Machine Learning InternMar 2026 – May 2026
NIELIT
Full Stack Web Development InternJune 2025
Company
Projects
Inventory App
Achievements
Hackathon finalist
"""
    profile = analyze_resume(make_pdf(sample))
    assert profile["contact"]["email"] == "alex@example.com"
    assert profile["education"]["cgpa"] == 8.2
    assert profile["education"]["degree"] == "B.Tech Computer Science"
    assert "Python" in profile["skills"]
    assert profile["skills"].count("React.js") == 1
    assert "React" not in profile["skills"]
    assert profile["experience"]["internship_count_hint"] == 2


def test_rejects_unreadable_pdf():
    from app.resume_parser import _extract_text
    import pytest
    with pytest.raises(ValueError):
        _extract_text(BytesIO(b"%PDF-invalid-but-short"))
