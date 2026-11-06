from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()

    from huggingface_hub import snapshot_download

    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=args.repo,
        revision=args.revision,
        local_dir=destination,
        local_dir_use_symlinks=False,
    )
    files = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or ".cache" in path.relative_to(destination).parts:
            continue
        files.append(
            {
                "path": path.relative_to(destination).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    manifest = {
        "repo_id": args.repo,
        "revision": args.revision,
        "installed_at": datetime.now(UTC).isoformat(),
        "files": files,
    }
    (destination / ".labor-case-pack.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"files": len(files), "bytes": sum(item["size"] for item in files)}))


if __name__ == "__main__":
    main()
