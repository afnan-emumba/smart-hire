import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICES = ["user", "job", "resume", "application", "notification"]

PACKAGES = {
    "smarthire_contracts": (REPO_ROOT / "contracts", SERVICES),
    "smarthire_shared": (REPO_ROOT / "shared", SERVICES),
}


def build_wheel(name: str, source_dir: Path) -> Path:
    dist_dir = source_dir / "dist"
    for stale_dir in (
        dist_dir,
        source_dir / "build",
        *source_dir.glob("*.egg-info"),
        *(source_dir / "src").glob("*.egg-info"),
    ):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(source_dir),
            "-w",
            str(dist_dir),
            "--no-deps",
        ],
        check=True,
    )
    wheels = list(dist_dir.glob(f"{name}-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected exactly one built wheel for {name}, found {wheels}")
    return wheels[0]


def vendor_wheel(wheel: Path, services: list[str]) -> None:
    for service in services:
        vendor_dir = REPO_ROOT / "services" / service / "vendor"
        vendor_dir.mkdir(exist_ok=True)
        for stale in vendor_dir.glob(f"{wheel.name.split('-')[0]}-*.whl"):
            stale.unlink()
        shutil.copy2(wheel, vendor_dir / wheel.name)
        print(f"vendored {wheel.name} -> services/{service}/vendor/")


def clear_unused_vendor(name: str, excluded_services: list[str]) -> None:
    for service in excluded_services:
        vendor_dir = REPO_ROOT / "services" / service / "vendor"
        for stale in vendor_dir.glob(f"{name}-*.whl"):
            stale.unlink()
            print(
                f"removed stale {stale.name} from services/{service}/vendor/ (not used there)"
            )


def main() -> None:
    for name, (source_dir, services) in PACKAGES.items():
        wheel = build_wheel(name, source_dir)
        vendor_wheel(wheel, services)
        clear_unused_vendor(name, [s for s in SERVICES if s not in services])

    print(
        "\nBuilt and vendored all packages. Run `docker compose build` to rebuild service images with them."
    )


if __name__ == "__main__":
    main()
