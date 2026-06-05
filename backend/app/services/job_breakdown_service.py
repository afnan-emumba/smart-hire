from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.schemas.job_breakdown import (
    Compensation,
    EducationRequirement,
    JobBreakdown,
    JobLocation,
    RequirementsBreakdown,
    Skill,
    Technology,
)
from app.utils.skill_extractor import SkillExtractor


class JobBreakdownService:
    _SECTION_ALIASES: dict[str, tuple[str, ...]] = {
        "title": ("job title", "title", "role"),
        "overview": ("summary", "overview", "job description", "about the role", "about us"),
        "location": ("location", "work location"),
        "employment_type": ("job type", "employment type", "engagement type"),
        "department": ("department", "team"),
        "job_category": ("category", "function", "job category"),
        "compensation": ("compensation", "salary", "salary range", "pay range"),
        "education": ("education", "education requirements"),
        "experience": ("experience", "experience required"),
        "application_deadline": ("application deadline", "apply by", "closing date"),
        "skills": ("skills", "technical skills", "required skills"),
        "requirements": (
            "requirements",
            "qualifications",
            "what we're looking for",
            "what we are looking for",
        ),
        "must_haves": ("must-have", "must-haves", "must have", "must haves"),
        "nice_to_haves": (
            "nice-to-have",
            "nice-to-haves",
            "nice to have",
            "nice to haves",
            "preferred",
            "preferred qualifications",
            "bonus",
        ),
        "responsibilities": ("responsibilities", "what you will do", "role responsibilities"),
        "benefits": ("benefits", "perks", "what we offer"),
    }
    _TECHNOLOGY_CATEGORIES: dict[str, str] = {
        "python": "language",
        "java": "language",
        "javascript": "language",
        "typescript": "language",
        "sql": "language",
        "fastapi": "framework",
        "django": "framework",
        "flask": "framework",
        "spring": "framework",
        "react": "framework",
        "node.js": "platform",
        "postgresql": "database",
        "mysql": "database",
        "sqlite": "database",
        "redis": "database",
        "aws": "cloud",
        "docker": "tool",
        "kubernetes": "platform",
        "kafka": "platform",
        "rabbitmq": "platform",
        "celery": "tool",
        "temporal": "platform",
        "git": "tool",
        "jira": "tool",
        "confluence": "tool",
        "google analytics": "tool",
    }
    _SOFT_SKILL_KEYWORDS = (
        "communication",
        "leadership",
        "stakeholder",
        "collaboration",
        "teamwork",
        "problem solving",
        "problem-solving",
        "analytical",
        "management",
        "mentoring",
    )
    _EMPLOYMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bfull[- ]?time\b", re.IGNORECASE), "full_time"),
        (re.compile(r"\bpart[- ]?time\b", re.IGNORECASE), "part_time"),
        (re.compile(r"\bcontract\b", re.IGNORECASE), "contract"),
        (re.compile(r"\btemporary\b", re.IGNORECASE), "temporary"),
        (re.compile(r"\bintern(ship)?\b", re.IGNORECASE), "internship"),
        (re.compile(r"\bfreelance\b", re.IGNORECASE), "freelance"),
    )
    _SENIORITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bprincipal\b", re.IGNORECASE), "principal"),
        (re.compile(r"\bstaff\b", re.IGNORECASE), "staff"),
        (re.compile(r"\blead\b", re.IGNORECASE), "lead"),
        (re.compile(r"\bsenior\b", re.IGNORECASE), "senior"),
        (re.compile(r"\bmid\b|\bintermediate\b", re.IGNORECASE), "mid"),
        (re.compile(r"\bjunior\b", re.IGNORECASE), "junior"),
        (re.compile(r"\bintern\b", re.IGNORECASE), "intern"),
        (re.compile(r"\bdirector\b", re.IGNORECASE), "director"),
    )
    _REMOTE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"\bon[- ]?site\b", re.IGNORECASE), "on_site"),
        (re.compile(r"\bhybrid\b", re.IGNORECASE), "hybrid"),
        (re.compile(r"\bremote\b", re.IGNORECASE), "remote"),
    )
    _CATEGORY_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
        (re.compile(r"\bbackend\b", re.IGNORECASE),
         "Engineering", "Backend Engineering"),
        (re.compile(r"\bfrontend\b", re.IGNORECASE),
         "Engineering", "Frontend Engineering"),
        (re.compile(r"\bfull[- ]?stack\b", re.IGNORECASE),
         "Engineering", "Full-Stack Engineering"),
        (re.compile(r"\bdevops\b|\bsre\b|\bplatform\b", re.IGNORECASE),
         "Engineering", "Platform Engineering"),
        (re.compile(r"\bdata engineer\b|\bdata scientist\b|\banalyst\b",
         re.IGNORECASE), "Data", "Data"),
        (re.compile(r"\bproduct manager\b|\bproduct owner\b",
         re.IGNORECASE), "Product", "Product Management"),
        (re.compile(r"\bdesigner\b|\bux\b|\bui\b", re.IGNORECASE), "Design", "Design"),
        (re.compile(r"\brecruit\b|\btalent\b|\bhr\b",
         re.IGNORECASE), "People", "People Operations"),
    )
    _YEARS_REQUIRED_PATTERN = re.compile(
        r"(?P<years>\d+)(?:\s*-\s*\d+)?\+?\s+(?:years?|yrs?)\s+of\s+experience", re.IGNORECASE)
    _CURRENCY_PATTERN = re.compile(
        r"(?P<currency>USD|EUR|GBP|AED|SAR|PKR|INR|\$|€|£)\s*(?P<min>[\d,]+)(?:\s*[-–to]{1,3}\s*(?P<max>[\d,]+))?",
        re.IGNORECASE,
    )
    _DEADLINE_PATTERNS: tuple[str, ...] = (
        "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y")

    @classmethod
    async def breakdown_job_description(cls, description: str) -> JobBreakdown:
        return (await cls.extract_job_profile(title=None, description=description))["breakdown"]

    @classmethod
    async def extract_job_profile(cls, *, title: str | None, description: str) -> dict[str, Any]:
        normalized_description = description.strip()
        sections = cls._collect_sections(normalized_description)
        skills = cls._extract_skills(sections)
        technologies = cls._extract_technologies(skills, sections)
        education_requirements = cls._extract_education_requirements(sections)
        location = cls._extract_location(sections)
        compensation = cls._extract_compensation(sections)
        requirements = cls._extract_requirements(sections)
        responsibilities = cls._extract_responsibilities(sections)
        benefits = cls._extract_benefits(sections)
        overview = cls._extract_overview(sections)
        years_of_experience_required = cls._extract_years_of_experience_required(
            sections)
        employment_type = cls._extract_employment_type(sections)
        seniority_level = cls._extract_seniority_level(
            title, normalized_description)
        department, job_category = cls._extract_department_and_category(
            title, sections)
        application_deadline = cls._extract_application_deadline(sections)

        return {
            "breakdown": JobBreakdown(
                overview=overview,
                skills=skills,
                technologies=technologies,
                education_requirements=education_requirements,
                requirements=requirements,
                responsibilities=responsibilities,
                location=location,
                compensation=compensation,
                benefits=benefits,
            ),
            "employment_type": employment_type,
            "seniority_level": seniority_level,
            "department": department,
            "job_category": job_category,
            "location": location,
            "compensation": compensation,
            "years_of_experience_required": years_of_experience_required,
            "application_deadline": application_deadline,
        }

    @classmethod
    def _extract_skills(cls, sections: dict[str, list[str]]):
        direct_skills = [
            Skill(
                name=cls._normalize_skill_item(skill_item),
                category=cls._classify_skill_category(skill_item),
                proficiency="intermediate",
                years_required=None,
            )
            for skill_item in sections.get("skills", [])
            if cls._normalize_skill_item(skill_item)
        ]
        inferred_skills = SkillExtractor.extract_skills(
            "\n".join(
                [
                    *sections.get("skills", []),
                    *sections.get("requirements", []),
                    *sections.get("must_haves", []),
                    *sections.get("nice_to_haves", []),
                ]
            )
        )
        return cls._merge_skills(direct_skills, inferred_skills)

    @classmethod
    def _extract_requirements(cls, sections: dict[str, list[str]]) -> RequirementsBreakdown:
        must_haves = list(sections.get("must_haves", []))
        nice_to_haves = list(sections.get("nice_to_haves", []))

        if not must_haves:
            must_haves = list(sections.get("requirements", []))

        return RequirementsBreakdown(
            must_haves=must_haves,
            nice_to_haves=nice_to_haves,
        )

    @classmethod
    def _extract_responsibilities(cls, sections: dict[str, list[str]]) -> list[str]:
        return list(sections.get("responsibilities", []))

    @classmethod
    def _extract_benefits(cls, sections: dict[str, list[str]]) -> list[str] | None:
        benefits = list(sections.get("benefits", []))
        return benefits or None

    @classmethod
    def _extract_overview(cls, sections: dict[str, list[str]]) -> str | None:
        overview_lines = sections.get("overview", [])
        if not overview_lines:
            return None
        return "\n".join(overview_lines)

    @classmethod
    def _extract_technologies(cls, skills: list[Skill], sections: dict[str, list[str]]) -> list[Technology]:
        technologies: list[Technology] = []
        seen: set[str] = set()

        for skill in skills:
            if skill.category != "technology":
                continue

            key = skill.name.casefold()
            seen.add(key)
            technologies.append(
                Technology(
                    name=skill.name,
                    category=cls._technology_category_for_name(skill.name),
                    required=True,
                )
            )

        for raw_item in sections.get("skills", []):
            normalized = cls._normalize_skill_item(raw_item)
            if not normalized:
                continue
            if cls._classify_skill_category(normalized) != "technology":
                continue

            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            technologies.append(
                Technology(
                    name=normalized,
                    category=cls._technology_category_for_name(normalized),
                    required=True,
                )
            )

        return technologies

    @classmethod
    def _extract_education_requirements(
        cls,
        sections: dict[str, list[str]],
    ) -> list[EducationRequirement]:
        lines = [
            *sections.get("education", []),
            *sections.get("requirements", []),
            *sections.get("must_haves", []),
        ]
        education_requirements: list[EducationRequirement] = []
        seen: set[tuple[str | None, tuple[str, ...]]] = set()

        for line in lines:
            lowered = line.casefold()
            level: str | None = None
            if "bachelor" in lowered:
                level = "bachelor"
            elif "master" in lowered:
                level = "master"
            elif "phd" in lowered or "doctorate" in lowered:
                level = "phd"
            elif "associate" in lowered:
                level = "associate"

            if level is None:
                continue

            fields_of_study = cls._extract_fields_of_study(line)
            dedupe_key = (level, tuple(field.casefold()
                          for field in fields_of_study))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            education_requirements.append(
                EducationRequirement(
                    level=level,
                    fields_of_study=fields_of_study,
                    required=True,
                )
            )

        return education_requirements

    @classmethod
    def _extract_location(cls, sections: dict[str, list[str]]) -> JobLocation | None:
        location_lines = sections.get("location", [])
        if not location_lines:
            return None

        raw_text = location_lines[0]
        remote_policy = "unknown"
        for pattern, value in cls._REMOTE_PATTERNS:
            if pattern.search(raw_text):
                remote_policy = value
                break

        location_text = raw_text
        parenthetical_match = re.search(r"\((?P<location>[^)]+)\)", raw_text)
        if parenthetical_match is not None:
            location_text = parenthetical_match.group("location")
        else:
            location_text = re.sub(
                r"\b(on[- ]?site|hybrid|remote)\b", "", raw_text, flags=re.IGNORECASE).strip(" ,-")

        city = state = country = None
        if location_text:
            parts = [part.strip()
                     for part in location_text.split(",") if part.strip()]
            if len(parts) >= 1:
                city = parts[0]
            if len(parts) >= 2:
                state = parts[1]
            if len(parts) >= 3:
                country = parts[2]

        return JobLocation(
            city=city,
            state=state,
            country=country,
            remote_policy=remote_policy,
            raw_text=raw_text,
        )

    @classmethod
    def _extract_compensation(cls, sections: dict[str, list[str]]) -> Compensation | None:
        compensation_lines = sections.get("compensation", [])
        benefits = cls._extract_benefits(sections)
        if not compensation_lines and not benefits:
            return None

        raw_text = " ".join(compensation_lines)
        currency = None
        min_amount = None
        max_amount = None
        interval = "unknown"

        if raw_text:
            match = cls._CURRENCY_PATTERN.search(raw_text)
            if match is not None:
                currency = cls._normalize_currency(match.group("currency"))
                min_amount = cls._parse_amount(match.group("min"))
                max_amount = cls._parse_amount(match.group(
                    "max")) if match.group("max") else None

            lowered = raw_text.casefold()
            if "hour" in lowered:
                interval = "hourly"
            elif "month" in lowered:
                interval = "monthly"
            elif "year" in lowered or "annual" in lowered:
                interval = "annual"
            elif "contract" in lowered:
                interval = "contract"

        return Compensation(
            currency=currency,
            min_amount=min_amount,
            max_amount=max_amount,
            interval=interval,
            additional_benefits=benefits or [],
        )

    @classmethod
    def _extract_years_of_experience_required(cls, sections: dict[str, list[str]]) -> int | None:
        lines = [
            *sections.get("experience", []),
            *sections.get("requirements", []),
            *sections.get("must_haves", []),
        ]
        years: list[int] = []

        for line in lines:
            match = cls._YEARS_REQUIRED_PATTERN.search(line)
            if match is None:
                continue
            years.append(int(match.group("years")))

        return min(years) if years else None

    @classmethod
    def _extract_employment_type(cls, sections: dict[str, list[str]]) -> str | None:
        lines = sections.get("employment_type", [])
        if not lines:
            return None

        raw_text = " ".join(lines)
        for pattern, employment_type in cls._EMPLOYMENT_PATTERNS:
            if pattern.search(raw_text):
                return employment_type

        return None

    @classmethod
    def _extract_seniority_level(cls, title: str | None, description: str) -> str | None:
        if not title:
            return None

        for pattern, seniority in cls._SENIORITY_PATTERNS:
            if pattern.search(title):
                return seniority

        return None

    @classmethod
    def _extract_department_and_category(
        cls,
        title: str | None,
        sections: dict[str, list[str]],
    ) -> tuple[str | None, str | None]:
        explicit_department = sections.get("department", [None])[0]
        explicit_category = sections.get("job_category", [None])[0]
        title_text = title or ""

        inferred_department = inferred_category = None
        for pattern, department, category in cls._CATEGORY_PATTERNS:
            if pattern.search(title_text):
                inferred_department = department
                inferred_category = category
                break

        return explicit_department or inferred_department, explicit_category or inferred_category

    @classmethod
    def _extract_application_deadline(cls, sections: dict[str, list[str]]) -> datetime | None:
        lines = sections.get("application_deadline", [])
        if not lines:
            return None

        raw_text = lines[0].strip()
        for pattern in cls._DEADLINE_PATTERNS:
            try:
                return datetime.strptime(raw_text, pattern).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", raw_text)
        if iso_match is not None:
            try:
                return datetime.strptime(iso_match.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        return None

    @classmethod
    def _collect_sections(cls, text: str) -> dict[str, list[str]]:
        sections: dict[str, list[str]] = {}
        active_section: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            matched_section, inline_content = cls._match_section_heading(line)
            if matched_section is not None:
                active_section = matched_section
                sections.setdefault(matched_section, [])
                if inline_content:
                    cleaned_inline = cls._clean_section_item(inline_content)
                    if cleaned_inline:
                        sections[matched_section].append(cleaned_inline)
                continue

            if active_section is None:
                active_section = "overview"
                sections.setdefault(active_section, [])

            cleaned_item = cls._clean_section_item(line)
            if cleaned_item:
                sections.setdefault(active_section, []).append(cleaned_item)

        return {
            section_name: cls._deduplicate(items)
            for section_name, items in sections.items()
        }

    @classmethod
    def _match_section_heading(cls, line: str) -> tuple[str | None, str | None]:
        for section_name, aliases in cls._SECTION_ALIASES.items():
            for alias in aliases:
                pattern = re.compile(
                    rf"^(?:#+\s*)?{re.escape(alias)}\s*:?\s*(.*)$", re.IGNORECASE)
                match = pattern.match(line)
                if match is None:
                    continue

                inline_content = match.group(1).strip() or None
                return section_name, inline_content

        return None, None

    @staticmethod
    def _clean_section_item(line: str) -> str | None:
        cleaned = re.sub(r"^(?:[-*•]\s+|\d+\.\s+)", "", line).strip()
        if not cleaned:
            return None
        return cleaned

    @staticmethod
    def _deduplicate(items: list[str]) -> list[str]:
        seen: set[str] = set()
        deduplicated: list[str] = []

        for item in items:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)

        return deduplicated

    @staticmethod
    def _normalize_skill_item(skill_item: str) -> str:
        return skill_item.strip().rstrip(".")

    @classmethod
    def _classify_skill_category(cls, skill_item: str) -> str:
        normalized = skill_item.strip().casefold()
        if any(keyword in normalized for keyword in cls._SOFT_SKILL_KEYWORDS):
            return "soft"
        if normalized in cls._TECHNOLOGY_CATEGORIES:
            return "technology"
        if normalized.replace(" ", "") in {key.replace(" ", "") for key in cls._TECHNOLOGY_CATEGORIES}:
            return "technology"
        return "domain"

    @classmethod
    def _technology_category_for_name(cls, name: str) -> str:
        return cls._TECHNOLOGY_CATEGORIES.get(name.casefold(), "other")

    @staticmethod
    def _extract_fields_of_study(line: str) -> list[str]:
        match = re.search(r"\b(?:in|of)\s+([A-Za-z,&/\- ]+)", line)
        if match is None:
            return []

        cleaned = match.group(1).strip().rstrip(".")
        cleaned = re.sub(r"\bor a related (?:field|eld)\b", "",
                         cleaned, flags=re.IGNORECASE).strip(" ,")
        if not cleaned:
            return []

        return [part.strip() for part in re.split(r",|/| and ", cleaned) if part.strip()]

    @staticmethod
    def _normalize_currency(currency: str) -> str:
        return {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
        }.get(currency.upper(), currency.upper())

    @staticmethod
    def _parse_amount(value: str | None) -> int | None:
        if value is None:
            return None
        return int(value.replace(",", ""))

    @staticmethod
    def _merge_skills(*skill_groups: list[Skill]) -> list[Skill]:
        merged_skills: list[Skill] = []
        seen: set[str] = set()

        for skill_group in skill_groups:
            for skill in skill_group:
                key = skill.name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                merged_skills.append(skill)

        return merged_skills
