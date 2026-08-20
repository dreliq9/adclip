"""Content-addressed local artifact storage."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from adclip.storage.database import Database, default_data_dir


@dataclass(frozen=True)
class ArtifactRecord:
    sha256: str
    path: Path
    size_bytes: int
    media_type: str | None = None
    original_name: str | None = None

    @property
    def uri(self) -> str:
        return f"artifact://sha256/{self.sha256}"


class ArtifactStore:
    """Immutable SHA-256-addressed artifact store shared across campaigns."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        database: Database | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else default_data_dir() / "artifacts" / "sha256"
        self.database = database or Database()

    def path_for(self, sha256: str) -> Path:
        if len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256.lower()):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        digest = sha256.lower()
        return self.root / digest[:2] / digest[2:4] / digest

    def put_bytes(
        self,
        payload: bytes,
        *,
        media_type: str | None = None,
        original_name: str | None = None,
    ) -> ArtifactRecord:
        digest = hashlib.sha256(payload).hexdigest()
        target = self.path_for(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_bytes(payload)
            temporary.replace(target)
        record = ArtifactRecord(
            sha256=digest,
            path=target,
            size_bytes=len(payload),
            media_type=media_type,
            original_name=original_name,
        )
        self._record(record)
        return record

    def put_file(
        self,
        source: str | Path,
        *,
        media_type: str | None = None,
    ) -> ArtifactRecord:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        sha256 = digest.hexdigest()
        target = self.path_for(sha256)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = target.with_name(f".{target.name}.tmp")
            shutil.copyfile(path, temporary)
            temporary.replace(target)
        resolved_media_type = media_type or mimetypes.guess_type(path.name)[0]
        record = ArtifactRecord(
            sha256=sha256,
            path=target,
            size_bytes=size,
            media_type=resolved_media_type,
            original_name=path.name,
        )
        self._record(record)
        return record

    def resolve(self, uri_or_sha256: str) -> Path:
        prefix = "artifact://sha256/"
        digest = uri_or_sha256[len(prefix):] if uri_or_sha256.startswith(prefix) else uri_or_sha256
        path = self.path_for(digest)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def _record(self, record: ArtifactRecord) -> None:
        self.database.migrate()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts(sha256, size_bytes, media_type, original_name, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    media_type = COALESCE(artifacts.media_type, excluded.media_type),
                    original_name = COALESCE(artifacts.original_name, excluded.original_name)
                """,
                (
                    record.sha256,
                    record.size_bytes,
                    record.media_type,
                    record.original_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
