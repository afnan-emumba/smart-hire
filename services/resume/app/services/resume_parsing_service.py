from __future__ import annotations

import re

from app.schemas.resume import (ResumeContact, ResumeLinks,
                                ResumeStructuredData, ResumeTextEntry)
from pydantic import AnyHttpUrl, TypeAdapter, ValidationError
from skills.skill_extractor import SkillExtractor

_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


class ResumeParsingService:
    _SECTION_ALIASES: dict[str, tuple[str, ...]] = {
        "summary": ("summary", "profile", "professional summary", "objective"),
        "skills": ("skills", "technical skills", "core competencies"),
        "experience": (
            "experience",
            "work experience",
            "professional experience",
            "employment history",
        ),
        "education": ("education",),
        "projects": ("projects",),
        "certifications": ("certifications",),
        "contact": ("contact",),
        "links": ("links",),
    }
    _EMAIL_PATTERN = re.compile(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    _PHONE_PATTERN = re.compile(
        r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3}[\s.-]?\d{3,4}"
    )
    _URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)

    @classmethod
    async def extract_resume_profile(cls, markdown: str) -> ResumeStructuredData:
        normalized_markdown = markdown.strip()
        sections = cls._collect_sections(normalized_markdown)
        return ResumeStructuredData(
            summary=cls._extract_summary(sections),
            skills=cls._extract_skills(sections, normalized_markdown),
            contact=cls._extract_contact(sections, normalized_markdown),
            education=cls._extract_list_section(sections, "education"),
            work_experience=cls._extract_list_section(sections, "experience"),
            projects=cls._extract_list_section(sections, "projects"),
            certifications=cls._extract_list_section(
                sections, "certifications"),
            links=cls._extract_links(sections, normalized_markdown),
            markdown=normalized_markdown,
        )

    @classmethod
    def _collect_sections(cls, markdown: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {key: []
                                          for key in cls._SECTION_ALIASES}
        current_section = "summary"

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("## "):
                heading = line[3:].strip().casefold()
                current_section = cls._section_key_for_heading(heading)
                sections.setdefault(current_section, [])
                continue

            if line.startswith("- "):
                line = line[2:].strip()

            sections.setdefault(current_section, []).append(line)

        return sections

    @classmethod
    def _section_key_for_heading(cls, heading: str) -> str:
        for section, aliases in cls._SECTION_ALIASES.items():
            if heading in aliases:
                return section
        return "summary"

    @staticmethod
    def _extract_summary(sections: dict[str, list[str]]) -> str | None:
        lines = sections.get("summary", [])
        if not lines:
            return None
        return "\n".join(lines[:3])

    @classmethod
    def _extract_skills(cls, sections: dict[str, list[str]], markdown: str) -> list[str]:
        explicit_skills = {
            cls._normalize_skill(skill)
            for skill in sections.get("skills", [])
            if cls._normalize_skill(skill)
        }
        inferred_skills = {
            skill.name
            for skill in SkillExtractor.extract_skills(markdown)
        }
        combined = explicit_skills | inferred_skills
        return sorted(combined)

    @classmethod
    def _extract_contact(cls, sections: dict[str, list[str]], markdown: str) -> ResumeContact:
        contact_text = "\n".join(
            [
                *sections.get("contact", []),
                *sections.get("summary", [])[:2],
                markdown.splitlines()[0] if markdown.splitlines() else "",
            ]
        )
        email_match = cls._EMAIL_PATTERN.search(markdown)
        phone_match = cls._PHONE_PATTERN.search(contact_text)
        location = None
        for line in sections.get("contact", []) + sections.get("summary", [])[:2]:
            if "@" in line or cls._PHONE_PATTERN.search(line) or cls._URL_PATTERN.search(line):
                continue
            if line:
                location = line
                break
        return ResumeContact(
            email=email_match.group(0) if email_match is not None else None,
            phone=phone_match.group(0) if phone_match is not None else None,
            location=location,
        )

    @classmethod
    def _extract_links(cls, sections: dict[str, list[str]], markdown: str) -> ResumeLinks:
        sources = [*sections.get("links", []), *
                   sections.get("contact", []), markdown]
        urls: list[str] = []
        for source in sources:
            urls.extend(match.group(0)
                        for match in cls._URL_PATTERN.finditer(source))

        values: dict[str, str] = {}
        for url in urls:
            if not cls._is_valid_url(url):
                continue
            lowered = url.casefold()
            if "linkedin.com" in lowered:
                values["linkedin"] = url
            elif "github.com" in lowered:
                values["github"] = url
            elif "portfolio" not in values:
                values["portfolio"] = url
            elif "website" not in values:
                values["website"] = url

        return ResumeLinks(**values)

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            _URL_ADAPTER.validate_python(url)
            return True
        except ValidationError:
            return False

    @staticmethod
    def _extract_list_section(sections: dict[str, list[str]], key: str) -> list[ResumeTextEntry]:
        return [ResumeTextEntry(raw_text=line) for line in sections.get(key, []) if line]

    @staticmethod
    def _normalize_skill(value: str) -> str | None:
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.startswith("-"):
            normalized = normalized[1:].strip()
        return normalized
