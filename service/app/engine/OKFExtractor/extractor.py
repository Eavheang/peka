from pathlib import Path


def write_okf_files(result: dict, base_dir: Path) -> None:
    files = result.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("OKF result must contain files")

    base_dir = base_dir.resolve()
    destinations: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get("path"), str):
            raise ValueError("Invalid OKF file")
        relative_path = Path(file["path"])
        content = file.get("content")
        destination = (base_dir / relative_path).resolve()

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
            or relative_path.parts[0] != "knowledge_base"
            or relative_path.suffix != ".md"
            or not destination.is_relative_to(base_dir)
            or destination in seen
            or not isinstance(content, str)
        ):
            raise ValueError(f"Unsafe path: {relative_path}")
        seen.add(destination)
        destinations.append((destination, content))

    for destination, content in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
