from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from contracts.profile import ProfileLinks

ProfileText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
SummaryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
SkillName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class EducationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: ProfileText
    degree: ProfileText | None = None
    field_of_study: ProfileText | None = None
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)

    @model_validator(mode="after")
    def validate_year_range(self) -> EducationEntry:
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.end_year < self.start_year
        ):
            raise ValueError(
                "education end_year must be greater than or equal to start_year"
            )
        return self


class WorkExperienceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: ProfileText
    title: ProfileText
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    description: SummaryText | None = None

    @model_validator(mode="after")
    def validate_year_range(self) -> WorkExperienceEntry:
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.end_year < self.start_year
        ):
            raise ValueError(
                "work_experience end_year must be greater than or equal to start_year"
            )
        return self


class CandidateLinks(ProfileLinks):
    model_config = ConfigDict(extra="forbid")


class CandidateContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: (
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)
        ]
        | None
    ) = None
    location: ProfileText | None = None


class MasterProfileData(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "summary": "Backend engineer focused on distributed systems and API platforms.",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
                "contact": {"phone": "+1-555-0198", "location": "Lahore, PK"},
                "education": [
                    {
                        "institution": "State University",
                        "degree": "BSc",
                        "field_of_study": "Computer Science",
                        "start_year": 2018,
                        "end_year": 2022,
                    }
                ],
                "work_experience": [
                    {
                        "company": "Acme Corp",
                        "title": "Software Engineer",
                        "start_year": 2022,
                        "end_year": 2024,
                        "description": "Built async APIs and hiring workflow integrations.",
                    }
                ],
                "links": {
                    "linkedin": "https://www.linkedin.com/in/example",
                    "github": "https://github.com/example",
                    "portfolio": "https://portfolio.example.com",
                },
            }
        },
    )

    summary: SummaryText | None = None
    skills: list[SkillName] = Field(default_factory=list)
    contact: CandidateContact = Field(default_factory=CandidateContact)
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    links: CandidateLinks = Field(default_factory=CandidateLinks)


class CandidateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    name: ProfileText
    master_profile_data: MasterProfileData = Field(default_factory=MasterProfileData)


class CandidateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    name: ProfileText | None = None
    master_profile_data: MasterProfileData | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_for_required_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            for field_name in ("email", "name", "master_profile_data"):
                if field_name in data and data[field_name] is None:
                    raise ValueError(f"{field_name} cannot be set to null")
        return data


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    email: EmailStr
    name: str
    master_profile_data: MasterProfileData
    created_at: datetime
    updated_at: datetime
