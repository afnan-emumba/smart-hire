from __future__ import annotations

import io
import os
import random
import string
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gevent import sleep as gevent_sleep
from gevent.lock import Semaphore
from locust import HttpUser, between, task
from locust.exception import StopUser


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def random_string(length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=length))


def random_email(prefix: str) -> str:
    return f"{prefix}-{random_string(10)}@example.com"


def build_headers(user_id: str, role: str) -> dict[str, str]:
    return {
        "X-User-ID": user_id,
        "X-User-Role": role,
    }


@dataclass
class SetupState:
    recruiter_id: str
    job_id: str


class SmartHireLoadTest(HttpUser):
    wait_time = between(
        _env_float("SMARTHIRE_LOCUST_WAIT_MIN", 1.0),
        _env_float("SMARTHIRE_LOCUST_WAIT_MAX", 3.0),
    )

    _setup_lock: Semaphore = Semaphore()
    _setup_state: SetupState | None = None
    _setup_error: str | None = None

    _job_ready_timeout_seconds = _env_int("SMARTHIRE_LOCUST_JOB_READY_TIMEOUT_SECONDS", 180)
    _job_ready_poll_interval_seconds = _env_float("SMARTHIRE_LOCUST_JOB_READY_POLL_SECONDS", 2.0)

    _cv_files: list[tuple[str, bytes]] = []
    _jd_bytes: bytes | None = None
    _jd_name: str = "JD 3.pdf"

    def on_start(self) -> None:
        self._load_files()
        self._ensure_test_job_ready()

        if self.__class__._setup_error is not None:
            raise StopUser(self.__class__._setup_error)

    def _load_files(self) -> None:
        cls = self.__class__
        if cls._cv_files and cls._jd_bytes is not None:
            return

        with cls._setup_lock:
            if cls._cv_files and cls._jd_bytes is not None:
                return

            samples_dir = Path(__file__).resolve().parents[2] / "samples"
            jd_path = samples_dir / cls._jd_name

            if not jd_path.exists():
                cls._setup_error = f"JD file not found at {jd_path}"
                return

            try:
                cls._jd_bytes = jd_path.read_bytes()
            except Exception as e:
                cls._setup_error = f"Failed to read sample JD file: {e}"
                return

            cv_names = ["CV 1.pdf", "CV 2.pdf", "CV 3.pdf"]
            cls._cv_files = []
            for name in cv_names:
                cv_path = samples_dir / name
                if not cv_path.exists():
                    cls._setup_error = f"CV file not found at {cv_path}"
                    return
                try:
                    cls._cv_files.append((name, cv_path.read_bytes()))
                except Exception as e:
                    cls._setup_error = f"Failed to read sample CV file {name}: {e}"
                    return

    def _ensure_test_job_ready(self) -> None:
        cls = self.__class__
        if cls._setup_state is not None or cls._setup_error is not None:
            return

        with cls._setup_lock:
            if cls._setup_state is not None or cls._setup_error is not None:
                return

            setup = self._run_setup_flow()
            if setup is None:
                cls._setup_error = "Failed to initialize recruiter/job bootstrap state"
                return

            cls._setup_state = setup

    def _run_setup_flow(self) -> SetupState | None:
        bootstrap_headers = build_headers(str(uuid.uuid4()), "RECRUITER")

        recruiter_payload = {
            "email": random_email("recruiter"),
            "name": f"Load Recruiter {random_string(5)}",
        }
        recruiter_response = self._post_json(
            "/recruiters",
            recruiter_payload,
            headers=bootstrap_headers,
            expected_statuses={201},
            name="setup::create_recruiter",
        )
        if recruiter_response is None:
            return None

        recruiter_id = recruiter_response.get("id")
        if not recruiter_id:
            return None

        recruiter_headers = build_headers(recruiter_id, "RECRUITER")
        job_payload = {
            "title": "Senior Software Engineer - Load Test",
            "description": "Own distributed backend services and event-driven hiring workflows.",
            "department": "Engineering",
            "job_category": "Backend",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
        }
        job_response = self._post_json(
            "/jobs",
            job_payload,
            headers=recruiter_headers,
            expected_statuses={201},
            name="setup::create_job",
        )
        if job_response is None:
            return None

        job_id = job_response.get("id")
        if not job_id:
            return None

        if not self._upload_job_description(job_id, recruiter_headers):
            return None

        publish_ok = self._post_no_body(
            f"/jobs/{job_id}/publish",
            headers=recruiter_headers,
            expected_statuses={202},
            name="setup::publish_job",
        )
        if not publish_ok:
            return None

        if not self._wait_until_job_ready(job_id, recruiter_headers):
            return None

        return SetupState(recruiter_id=recruiter_id, job_id=job_id)

    def _wait_until_job_ready(self, job_id: str, headers: dict[str, str]) -> bool:
        deadline = time.time() + float(self._job_ready_timeout_seconds)
        while time.time() < deadline:
            response = self.client.get(
                f"/jobs/{job_id}",
                headers=headers,
                name="setup::poll_job",
            )
            if response.status_code == 200:
                try:
                    payload = response.json()
                    if payload.get("status", "").lower() == "ready":
                        return True
                except ValueError:
                    pass
            gevent_sleep(self._job_ready_poll_interval_seconds)
        return False

    def _upload_job_description(self, job_id: str, headers: dict[str, str]) -> bool:
        cls = self.__class__
        if cls._jd_bytes is None:
            return False

        with self.client.post(
            f"/jobs/{job_id}/description-file",
            headers=headers,
            files={"description_file": (cls._jd_name, io.BytesIO(cls._jd_bytes), "application/pdf")},
            name="setup::upload_job_description",
            catch_response=True,
        ) as response:
            if response.status_code == 0:
                return False

            if response.status_code not in {200, 201, 202}:
                response.failure(f"Failed to upload JD for job {job_id}: {response.status_code}")
                return False

            response.success()
            return True

    @task
    def candidate_application_flow(self) -> None:
        setup_state = self.__class__._setup_state
        if setup_state is None:
            return

        candidate_create_headers = build_headers(str(uuid.uuid4()), "CANDIDATE")
        candidate_payload = {
            "email": random_email("candidate"),
            "name": "Load Candidate",
            "master_profile_data": {
                "summary": "Backend engineer experienced with event-driven systems",
                "skills": ["Python", "FastAPI", "PostgreSQL"],
            },
        }
        candidate_response = self._post_json(
            "/candidates",
            candidate_payload,
            headers=candidate_create_headers,
            expected_statuses={201},
            name="candidate::create",
        )
        if candidate_response is None:
            return

        candidate_id = candidate_response.get("id")
        if not candidate_id:
            return

        candidate_headers = build_headers(candidate_id, "CANDIDATE")
        application_response = self._post_json(
            "/applications",
            {"job_id": setup_state.job_id},
            headers=candidate_headers,
            expected_statuses={201},
            name="application::create",
        )
        if application_response is None:
            return

        application_id = application_response.get("id")
        if not application_id:
            return

        if not self._upload_resume(candidate_headers, application_id):
            return
        self._submit_application(candidate_headers, application_id)

    def _upload_resume(self, headers: dict[str, str], application_id: str) -> bool:
        cls = self.__class__
        if not cls._cv_files:
            return False

        cv_name, cv_bytes = random.choice(cls._cv_files)

        with self.client.post(
            f"/applications/{application_id}/resume",
            headers=headers,
            files={"resume": (cv_name, io.BytesIO(cv_bytes), "application/pdf")},
            name="application::upload_resume",
            catch_response=True,
        ) as response:
            if response.status_code == 0:
                return False
            if response.status_code not in {200, 201, 202}:
                response.failure(f"Failed to upload Resume: {response.status_code}")
                return False
            response.success()
            return True

    def _submit_application(self, headers: dict[str, str], application_id: str) -> None:
        with self.client.post(
            f"/applications/{application_id}/submit",
            headers=headers,
            name="application::submit",
            catch_response=True,
        ) as response:
            if response.status_code == 0:
                return
            if response.status_code not in {200, 202}:
                response.failure(f"Failed to submit application: {response.status_code}")
                return
            response.success()

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
        expected_statuses: set[int],
        name: str,
    ) -> dict[str, Any] | None:
        with self.client.post(path, json=payload, headers=headers, name=name, catch_response=True) as response:
            if response.status_code == 0:
                return None

            if response.status_code not in expected_statuses:
                response.failure(
                    f"Unexpected status {response.status_code} for {path}; expected {sorted(expected_statuses)}"
                )
                return None

            try:
                body = response.json()
            except ValueError:
                response.failure(f"Invalid JSON response for {path}")
                return None

            response.success()
            return body

    def _post_no_body(
        self,
        path: str,
        *,
        headers: dict[str, str],
        expected_statuses: set[int],
        name: str,
    ) -> bool:
        with self.client.post(path, headers=headers, name=name, catch_response=True) as response:
            if response.status_code == 0:
                return False

            if response.status_code not in expected_statuses:
                response.failure(
                    f"Unexpected status {response.status_code} for {path}; expected {sorted(expected_statuses)}"
                )
                return False

            response.success()
            return True