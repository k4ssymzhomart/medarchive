"""CLI утилиты: сидирование справочника, локальный прогон архива (раздел 17).

Использование:
    python -m app.cli seed-reference [path]   # загрузить справочник (или синтетический)
    python -m app.cli ingest <dir|file|zip>   # зарегистрировать и обработать локально
    python -m app.cli reembed                 # досчитать эмбеддинги услуг
"""

from __future__ import annotations

import os
import sys

from app.database import SessionLocal
from app.normalization.reference_loader import (
    build_synthetic_reference,
    embed_missing,
    load_reference_records,
    upsert_services,
)


def seed_reference(args: list[str]) -> None:
    db = SessionLocal()
    try:
        path = args[0] if args else os.environ.get("REFERENCE_PATH", "")
        if path and os.path.exists(path):
            records = load_reference_records(path)
            added = upsert_services(db, records, compute_embeddings=True)
            print(f"Справочник загружен из {path}: добавлено услуг {added}")
        else:
            added = build_synthetic_reference(db)
            embedded = embed_missing(db)
            print(
                f"Финального справочника нет. Синтетический собран из прайсов: "
                f"услуг {added}, эмбеддингов {embedded}"
            )
    finally:
        db.close()


def ingest(args: list[str]) -> None:
    if not args:
        print("Укажите путь к файлу, директории или ZIP")
        return
    from app.services.document_service import process_document
    from app.services.upload_service import ingest_paths, ingest_zip

    target = args[0]
    db = SessionLocal()
    try:
        if os.path.isdir(target):
            paths = [
                (os.path.join(target, n), n)
                for n in sorted(os.listdir(target))
                if os.path.isfile(os.path.join(target, n))
            ]
            docs, skipped = ingest_paths(db, paths, enqueue=False)
        elif target.lower().endswith(".zip"):
            docs, skipped = ingest_zip(db, target, enqueue=False)
        else:
            docs, skipped = ingest_paths(db, [(target, os.path.basename(target))], enqueue=False)

        print(f"Зарегистрировано {len(docs)} документов, дубликатов {len(skipped)}")
        for doc in docs:
            print(f"  обработка {doc.file_name} ...")
            res = process_document(db, doc.doc_id)
            print(f"    статус={res.parse_status.value} позиций={res.item_count} ocr={res.ocr_applied}")
        # После прогона можно собрать синтетический справочник и пересопоставить.
    finally:
        db.close()


def reembed(_args: list[str]) -> None:
    db = SessionLocal()
    try:
        n = embed_missing(db)
        print(f"Досчитано эмбеддингов: {n}")
    finally:
        db.close()


COMMANDS = {"seed-reference": seed_reference, "ingest": ingest, "reembed": reembed}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Команды: " + ", ".join(COMMANDS))
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
