from pathlib import Path


def resolve_path(company_folder: str, relative_path: str) -> Path:
    base = Path(company_folder).resolve()
    return (base / relative_path).resolve()


def is_inside_folder(company_folder: str, candidate: Path) -> bool:
    base = Path(company_folder).resolve()
    return candidate == base or base in candidate.parents
