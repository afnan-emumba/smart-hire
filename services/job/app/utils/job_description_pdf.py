from __future__ import annotations

from pdf.markdown_converter import PdfMarkdownConverter


class JobDescriptionPdfConverter(PdfMarkdownConverter):
    _SECTION_HEADINGS: dict[str, str] = {
        "job title": "Job Title",
        "location": "Location",
        "job type": "Job Type",
        "employment type": "Employment Type",
        "department": "Department",
        "category": "Category",
        "summary": "Summary",
        "overview": "Overview",
        "job description": "Overview",
        "responsibilities": "Responsibilities",
        "requirements": "Requirements",
        "skills": "Skills",
        "education": "Education",
        "experience": "Experience",
        "qualifications": "Qualifications",
        "benefits": "Benefits",
        "compensation": "Compensation",
        "salary": "Compensation",
        "salary range": "Compensation",
        "application deadline": "Application Deadline",
        "preferred qualifications": "Preferred Qualifications",
        "nice to have": "Nice To Have",
        "nice-to-have": "Nice To Have",
        "must have": "Must Have",
        "must-have": "Must Have",
    }
    _EMPTY_TEXT_ERROR = "Unable to extract text from the uploaded PDF"
    _NO_CONTENT_ERROR = "Uploaded PDF does not contain readable job description text"
