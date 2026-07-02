from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader


class ResumePdfConverter:
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

    @classmethod
    def convert_pdf_to_markdown(cls, file_bytes: bytes) -> str:
        reader = PdfReader(BytesIO(file_bytes))
        extracted_pages = [page.extract_text() or "" for page in reader.pages]
        raw_text = "\n\n".join(extracted_pages).strip()
        if not raw_text:
            raise ValueError("Unable to extract text from the uploaded PDF")

        normalized_lines = cls._normalize_lines(raw_text)
        if not normalized_lines:
            raise ValueError("Uploaded PDF does not contain readable resume text")

        return "\n".join(normalized_lines)

    @classmethod
    def _normalize_lines(cls, raw_text: str) -> list[str]:
        normalized_lines: list[str] = []

        for raw_line in raw_text.splitlines():
            line = raw_line.replace("\x00", "")
            line = (
                line.replace("â€™", "'")
                .replace("â€œ", '"')
                .replace("â€", '"')
                .replace("â€“", "-")
            )
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue

            heading = cls._normalize_heading(line)
            if heading is not None:
                if normalized_lines and normalized_lines[-1] != "":
                    normalized_lines.append("")
                normalized_lines.append(f"## {heading}")
                continue

            bullet_match = re.match(r"^(?:[-*•]|•)\s+(.*)$", line)
            if bullet_match is not None:
                normalized_lines.append(f"- {bullet_match.group(1).strip()}")
                continue

            normalized_lines.append(line)

        return cls._collapse_blank_lines(normalized_lines)

    @classmethod
    def _normalize_heading(cls, line: str) -> str | None:
        normalized = line.rstrip(":").strip()
        key = normalized.casefold()
        return cls._SECTION_HEADINGS.get(key)

    @staticmethod
    def _collapse_blank_lines(lines: list[str]) -> list[str]:
        collapsed: list[str] = []
        previous_blank = False

        for line in lines:
            is_blank = not line
            if is_blank and previous_blank:
                continue
            collapsed.append(line)
            previous_blank = is_blank

        while collapsed and not collapsed[0]:
            collapsed.pop(0)
        while collapsed and not collapsed[-1]:
            collapsed.pop()

        return collapsed
