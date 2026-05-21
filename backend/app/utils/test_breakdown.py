from __future__ import annotations

import asyncio
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.job_breakdown_service import JobBreakdownService
from app.utils.job_description_pdf import JobDescriptionPdfConverter


SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"


async def main() -> None:
    for pdf_path in sorted(SAMPLES_DIR.glob("JD *.pdf")):
        markdown = JobDescriptionPdfConverter.convert_pdf_to_markdown(pdf_path.read_bytes())
        title_hint = _extract_title_hint(markdown) or pdf_path.stem
        profile = await JobBreakdownService.extract_job_profile(title=title_hint, description=markdown)
        print(f"=== {pdf_path.name} ===")
        print(markdown)
        print()
        print(profile["breakdown"].model_dump_json(indent=2))
        print()
        print({
            "employment_type": profile["employment_type"],
            "seniority_level": profile["seniority_level"],
            "department": profile["department"],
            "job_category": profile["job_category"],
            "location": profile["location"].model_dump() if profile["location"] else None,
            "compensation": profile["compensation"].model_dump() if profile["compensation"] else None,
            "years_of_experience_required": profile["years_of_experience_required"],
            "application_deadline": profile["application_deadline"].isoformat() if profile["application_deadline"] else None,
        })
        print()


def _extract_title_hint(markdown: str) -> str | None:
    for line in markdown.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if not normalized.lower().startswith("job title:"):
            continue

        title = normalized.split(":", 1)[1].strip()
        if title.lower().startswith("job title:"):
            title = title.split(":", 1)[1].strip()
        return title or None

    return None



if __name__ == "__main__":
    asyncio.run(main())