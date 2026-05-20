from __future__ import annotations

import re

from app.schemas.job_breakdown import JobBreakdown, RequirementsBreakdown, Skill
from app.utils.skill_extractor import SkillExtractor


class JobBreakdownService:
    _SECTION_ALIASES: dict[str, tuple[str, ...]] = {
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

    @classmethod
    async def breakdown_job_description(cls, description: str) -> JobBreakdown:
        normalized_description = description.strip()
        sections = cls._collect_sections(normalized_description)
        return JobBreakdown(
            skills=cls._extract_skills(sections),
            requirements=cls._extract_requirements(sections),
            responsibilities=cls._extract_responsibilities(sections),
            benefits=cls._extract_benefits(sections),
        )

    @classmethod
    def _extract_skills(cls, sections: dict[str, list[str]]):
        direct_skills = [
            Skill(
                name=cls._normalize_skill_item(skill_item),
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
                continue

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
                pattern = re.compile(rf"^(?:#+\s*)?{re.escape(alias)}\s*:?\s*(.*)$", re.IGNORECASE)
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