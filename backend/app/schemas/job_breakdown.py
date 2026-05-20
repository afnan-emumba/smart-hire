from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SkillProficiency = Literal["entry", "intermediate", "expert"]


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    proficiency: SkillProficiency
    years_required: int | None = Field(default=None, ge=0)


class RequirementsBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)


class JobBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[Skill] = Field(default_factory=list)
    requirements: RequirementsBreakdown = Field(default_factory=RequirementsBreakdown)
    responsibilities: list[str] = Field(default_factory=list)
    benefits: list[str] | None = None