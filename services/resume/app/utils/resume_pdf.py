from __future__ import annotations

from pdf.markdown_converter import PdfMarkdownConverter


class ResumePdfConverter(PdfMarkdownConverter):
    _SECTION_HEADINGS: dict[str, str] = {
        "summary": "Summary",
        "profile": "Summary",
        "professional summary": "Summary",
        "objective": "Summary",
        "skills": "Skills",
        "technical skills": "Skills",
        "core competencies": "Skills",
        "experience": "Experience",
        "work experience": "Experience",
        "professional experience": "Experience",
        "employment history": "Experience",
        "education": "Education",
        "projects": "Projects",
        "certifications": "Certifications",
        "contact": "Contact",
        "links": "Links",
    }
    _EMPTY_TEXT_ERROR = "Unable to extract text from the uploaded PDF"
    _NO_CONTENT_ERROR = "Uploaded PDF does not contain readable resume text"
