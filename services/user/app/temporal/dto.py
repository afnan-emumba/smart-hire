"""Workflow and activity payloads for the user deletion cascades.

Mock auth is header-based, so a cascade activity has no ambient ``CurrentUser``
once the HTTP request that started the workflow has returned. Every payload
therefore carries the originating actor explicitly, and activities rebuild a
``CurrentUser`` from it before calling downstream services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CandidateDeletionInput:
    candidate_id: str
    actor_user_id: str
    actor_role: str


@dataclass
class RecruiterDeletionInput:
    recruiter_id: str
    actor_user_id: str
    actor_role: str


@dataclass
class JobDeletionInput:
    job_id: str
    actor_user_id: str
    actor_role: str
