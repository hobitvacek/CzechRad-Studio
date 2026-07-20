"""QGIS-independent discovery, stability tracking and safe LOG archiving."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import shutil
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    path: Path
    size: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class ArchiveResult:
    source: Path
    destination: Path
    digest: str
    copied: bool


def scan_log_files(folder: str | Path) -> tuple[FileSnapshot, ...]:
    """Return LOG files recursively without modifying or opening them for write."""

    root = Path(folder)
    if not root.is_dir():
        raise FileNotFoundError(f"sledovaná složka není dostupná: {root}")
    snapshots = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".log":
            stat = path.stat()
            snapshots.append(FileSnapshot(path, stat.st_size, stat.st_mtime_ns))
    return tuple(sorted(snapshots, key=lambda item: str(item.path).casefold()))


class StableFileTracker:
    """Emit each file revision after repeated identical observations."""

    def __init__(self, required_observations: int = 2):
        if required_observations < 2:
            raise ValueError("required_observations must be at least two")
        self.required_observations = required_observations
        self._observed: dict[Path, tuple[int, int, int]] = {}
        self._emitted: dict[Path, tuple[int, int]] = {}

    def observe(self, folder: str | Path) -> tuple[Path, ...]:
        snapshots = scan_log_files(folder)
        current_paths = {item.path for item in snapshots}
        ready = []
        for item in snapshots:
            signature = (item.size, item.modified_ns)
            previous = self._observed.get(item.path)
            count = previous[2] + 1 if previous and previous[:2] == signature else 1
            self._observed[item.path] = (*signature, count)
            if (
                count >= self.required_observations
                and self._emitted.get(item.path) != signature
            ):
                self._emitted[item.path] = signature
                ready.append(item.path)

        for path in tuple(self._observed):
            if path not in current_paths:
                self._observed.pop(path, None)
                self._emitted.pop(path, None)
        return tuple(ready)


def file_digest(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _collision_name(source: Path, archive: Path, index: int) -> Path:
    if index == 0:
        return archive / source.name
    return archive / f"{source.stem}-{index}{source.suffix}"


def archive_log(source: str | Path, archive_folder: str | Path) -> ArchiveResult:
    """Copy one LOG safely, deduplicating content and numbering name collisions."""

    source_path = Path(source).resolve()
    archive = Path(archive_folder).resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".log":
        raise ValueError(f"není platný LOG soubor: {source_path}")
    if archive == source_path.parent or archive in source_path.parents:
        raise ValueError("archiv musí být mimo zdrojovou složku nebo kartu")
    archive.mkdir(parents=True, exist_ok=True)

    digest = file_digest(source_path)
    for existing in archive.rglob("*"):
        if existing.is_file() and existing.suffix.lower() == ".log":
            if file_digest(existing) == digest:
                return ArchiveResult(source_path, existing, digest, False)

    index = 0
    destination = _collision_name(source_path, archive, index)
    while destination.exists():
        index += 1
        destination = _collision_name(source_path, archive, index)

    temporary = archive / f".{destination.name}.{uuid4().hex}.tmp"
    try:
        shutil.copy2(source_path, temporary)
        if file_digest(temporary) != digest:
            raise OSError("kontrolní otisk kopie se neshoduje se zdrojem")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return ArchiveResult(source_path, destination, digest, True)


def archive_ready_logs(
    tracker: StableFileTracker,
    source_folder: str | Path,
    archive_folder: str | Path,
) -> tuple[ArchiveResult, ...]:
    return tuple(
        archive_log(path, archive_folder)
        for path in tracker.observe(source_folder)
    )

