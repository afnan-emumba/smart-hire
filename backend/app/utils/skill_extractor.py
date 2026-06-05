from __future__ import annotations

import re

from app.schemas.job_breakdown import Skill


class SkillExtractor:
    SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
        "Python": ("python",),
        "FastAPI": ("fastapi",),
        "Django": ("django",),
        "Flask": ("flask",),
        "Java": ("java",),
        "Spring": ("spring", "spring boot"),
        "SQL": ("sql",),
        "MySQL": ("mysql",),
        "SQLite": ("sqlite",),
        "PostgreSQL": ("postgresql", "postgres"),
        "AWS": ("aws", "amazon web services"),
        "Docker": ("docker",),
        "Kubernetes": ("kubernetes", "k8s"),
        "React": ("react", "react.js", "reactjs"),
        "Node.js": ("node.js", "nodejs", "node"),
        "TypeScript": ("typescript",),
        "JavaScript": ("javascript",),
        "Redis": ("redis",),
        "Kafka": ("kafka",),
        "RabbitMQ": ("rabbitmq",),
        "Celery": ("celery",),
        "Temporal": ("temporal",),
        "Git": ("git",),
        "Jira": ("jira",),
        "Confluence": ("confluence",),
        "Google Analytics": ("google analytics",),
    }

    _EXPERT_KEYWORDS = re.compile(
        r"\b(expert|advanced|senior|lead|deep expertise|highly proficient)\b")
    _INTERMEDIATE_KEYWORDS = re.compile(
        r"\b(intermediate|proficient|strong|solid|hands[- ]on|practical experience)\b"
    )
    _ENTRY_KEYWORDS = re.compile(
        r"\b(entry|junior|basic|familiar|working knowledge)\b")
    _YEARS_PATTERN = re.compile(r"(?P<years>\d+)\+?\s*(?:years?|yrs?)")

    @classmethod
    def extract_skills(cls, text: str) -> list[Skill]:
        extracted_skills: list[Skill] = []
        lowered_text = text.lower()

        for skill_name, keywords in cls.SKILL_KEYWORDS.items():
            context = cls._build_skill_context(lowered_text, keywords)
            if context is None:
                continue

            extracted_skills.append(
                Skill(
                    name=skill_name,
                    category="technology",
                    proficiency=cls._infer_proficiency(context),
                    years_required=cls._infer_years_required(context),
                )
            )

        return extracted_skills

    @staticmethod
    def _build_skill_context(text: str, keywords: tuple[str, ...]) -> str | None:
        matching_lines: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            for keyword in keywords:
                pattern = re.compile(
                    rf"(?<!\w){re.escape(keyword.lower())}(?!\w)")
                if pattern.search(line):
                    matching_lines.append(line)
                    break

        if not matching_lines:
            return None

        return " ".join(matching_lines)

    @classmethod
    def _infer_proficiency(cls, context: str) -> str:
        if cls._EXPERT_KEYWORDS.search(context):
            return "expert"
        if cls._INTERMEDIATE_KEYWORDS.search(context):
            return "intermediate"
        if cls._ENTRY_KEYWORDS.search(context):
            return "entry"

        years_required = cls._infer_years_required(context)
        if years_required is not None:
            if years_required >= 5:
                return "expert"
            if years_required >= 3:
                return "intermediate"

        return "intermediate"

    @classmethod
    def _infer_years_required(cls, context: str) -> int | None:
        match = cls._YEARS_PATTERN.search(context)
        if match is None:
            return None
        return int(match.group("years"))
