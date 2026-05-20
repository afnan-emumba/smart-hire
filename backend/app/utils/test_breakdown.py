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
        breakdown = await JobBreakdownService.breakdown_job_description(markdown)
        print(f"=== {pdf_path.name} ===")
        print(markdown)
        print()
        print(breakdown.model_dump_json(indent=2))
        print()


if __name__ == "__main__":
    asyncio.run(main())