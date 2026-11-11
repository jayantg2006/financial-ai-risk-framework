from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_RAG_Application"))
from fdia.ingestion import extract_pdf
from fdia.rag import ingest_json_documents, load_chunks


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_manifest(src: Path, pdfs: list[Path], metadata_dir: str | None) -> list[dict]:
    items = []
    for pdf in pdfs:
        sidecar_dir = Path(metadata_dir) if metadata_dir else pdf.parent
        sidecar = sidecar_dir / f"{pdf.stem}.metadata.json"
        if not sidecar.exists():
            raise SystemExit(f"Missing metadata sidecar: {sidecar}")
        for kind, path in (("pdf", pdf), ("metadata", sidecar)):
            try:
                rel = path.relative_to(src).as_posix()
            except ValueError:
                rel = str(path.resolve())
            items.append({"kind": kind, "path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and index approved JSON/PDF financial reports, preserving page/table provenance")
    parser.add_argument("--input", default=str(ROOT / "02_Data_and_Documents/raw/annual_reports"))
    parser.add_argument("--output", default=str(ROOT / "02_Data_and_Documents/processed/chunks.jsonl"))
    parser.add_argument("--metadata", help="JSON sidecar for a single PDF")
    parser.add_argument("--metadata-dir", help="Directory of <pdf-stem>.metadata.json sidecars for folder ingestion")
    parser.add_argument("--extract-tables", action="store_true", help="Run PyMuPDF table detection on every PDF page; this can be very slow. Page text is extracted by default.")
    parser.add_argument("--reuse-if-current", action="store_true", help="Reuse the output index only when its content-hash manifest matches the current PDFs and metadata sidecars.")
    args = parser.parse_args()
    src = Path(args.input)
    out = Path(args.output)
    if not src.exists():
        raise SystemExit(f"Input path not found: {src}")

    if src.is_file() and src.suffix.lower() == ".pdf":
        if not args.metadata:
            raise SystemExit("A single PDF requires --metadata JSON with document_id, company, financial_year, document_type, source_url, and publication_date.")
        extracted = src.with_suffix(".extracted.json")
        extract_pdf(src, json.loads(Path(args.metadata).read_text(encoding="utf-8")), extracted, extract_tables=args.extract_tables)
        chunks = ingest_json_documents(extracted, out)
        print(f"Created {len(chunks)} chunks from {src.name}")
        return 0

    if src.is_file() and src.suffix.lower() == ".json":
        chunks = ingest_json_documents(src, out)
        print(f"Created {len(chunks)} chunks from {src.name}")
        return 0

    if not src.is_dir():
        raise SystemExit("Input must be a JSON/PDF file or a directory.")

    pdfs = sorted(src.rglob("*.pdf"))
    metadata_by_pdf = {}
    for pdf in pdfs:
        meta_dir = Path(args.metadata_dir) if args.metadata_dir else pdf.parent
        sidecar = meta_dir / f"{pdf.stem}.metadata.json"
        if not sidecar.exists():
            raise SystemExit(f"Missing metadata sidecar: {sidecar}")
        metadata_by_pdf[pdf] = sidecar

    manifest_path = out.with_name("chunks_manifest.json")
    fingerprints = source_manifest(src, pdfs, args.metadata_dir) if pdfs else []
    if args.reuse_if_current and out.exists() and pdfs and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            output_matches = manifest.get("output_sha256") == sha256_file(out)
            if manifest.get("sources") == fingerprints and output_matches and manifest.get("extract_tables", False) == args.extract_tables:
                chunks = load_chunks(out)
                print(f"Reused current index: {len(chunks)} chunks from {len(pdfs)} PDFs (content hashes match).")
                return 0
        except (OSError, ValueError, TypeError):
            pass

    # Backward-compatible bootstrap for an older packaged index that predates the hash manifest.
    # Once this legacy index is accepted, save hashes so future reuse is timestamp-independent.
    if args.reuse_if_current and out.exists() and pdfs and not manifest_path.exists() and not args.extract_tables:
        source_paths = [p for p in pdfs] + list(metadata_by_pdf.values())
        if out.stat().st_mtime >= max(p.stat().st_mtime for p in source_paths):
            chunks = load_chunks(out)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(json.dumps({"schema_version": 1, "sources": fingerprints, "extract_tables": False, "chunk_count": len(chunks), "output_sha256": sha256_file(out)}, indent=2) + "\n", encoding="utf-8")
            print(f"Reused current index: {len(chunks)} chunks from {len(pdfs)} PDFs; initialized content-hash manifest.")
            return 0

    for pdf, sidecar in metadata_by_pdf.items():
        extract_pdf(pdf, json.loads(sidecar.read_text(encoding="utf-8")), pdf.with_suffix(".extracted.json"), extract_tables=args.extract_tables)

    # Stage payload JSON only; metadata sidecars are not page content. Flatten paths to avoid collisions.
    with tempfile.TemporaryDirectory(prefix="fdia-ingest-") as tmp:
        stage = Path(tmp)
        for file in sorted(src.rglob("*.json")):
            if file.name.endswith(".metadata.json"):
                continue
            prefix = file.parent.relative_to(src).as_posix().replace("/", "__")
            name = (prefix + "__" if prefix not in {"", ".", ".."} else "") + file.name
            shutil.copy2(file, stage / name)
        chunks = ingest_json_documents(stage, out)

    if not chunks:
        raise SystemExit("No approved document chunks were produced. Check report PDFs, metadata sidecars, approval status, or text extraction flags.")
    if pdfs:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"schema_version": 1, "sources": fingerprints, "extract_tables": args.extract_tables, "chunk_count": len(chunks), "output_sha256": sha256_file(out)}, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(chunks)} page-aware text/table chunks from {len(pdfs)} PDFs at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
