from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SkillProficiency = Literal["entry", "intermediate", "expert"]
SkillCategory = Literal["technology", "domain", "soft"]
TechnologyCategory = Literal["language", "framework", "database", "cloud", "tool", "platform", "other"]
RemotePolicy = Literal["remote", "hybrid", "on_site", "unknown"]
CompensationInterval = Literal["hourly", "monthly", "annual", "contract", "unknown"]


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    category: SkillCategory = "domain"
    proficiency: SkillProficiency
    years_required: int | None = Field(default=None, ge=0)


class Technology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    category: TechnologyCategory = "other"
    required: bool = True


class EducationRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str | None = Field(default=None, max_length=50)
    fields_of_study: list[str] = Field(default_factory=list)
    required: bool = True


class JobLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    remote_policy: RemotePolicy = "unknown"
    raw_text: str | None = Field(default=None, max_length=255)


class Compensation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str | None = Field(default=None, min_length=3, max_length=3)
    min_amount: int | None = Field(default=None, ge=0)
    max_amount: int | None = Field(default=None, ge=0)
    interval: CompensationInterval = "unknown"
    additional_benefits: list[str] = Field(default_factory=list)


class RequirementsBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)


class JobBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str | None = None
    skills: list[Skill] = Field(default_factory=list)
    technologies: list[Technology] = Field(default_factory=list)
    education_requirements: list[EducationRequirement] = Field(default_factory=list)
    requirements: RequirementsBreakdown = Field(default_factory=RequirementsBreakdown)
    responsibilities: list[str] = Field(default_factory=list)
    location: JobLocation | None = None
    compensation: Compensation | None = None
    benefits: list[str] | None = None