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


def embed_items(_args: list[str]) -> None:
    """Пакетно греет эмбеддинги уникальных названий активных позиций (в ai_cache).

    Делает дорогой шаг (эмбеддинги) одним пакетным вызовом на ~500 строк вместо
    тысяч одиночных в каскаде. После этого rematch берёт их из кэша.
    """
    from sqlalchemy import select

    from app.models import PriceItem
    from app.normalization import embeddings as emb

    db = SessionLocal()
    try:
        names = (
            db.execute(
                select(PriceItem.service_name_raw)
                .where(PriceItem.is_active.is_(True))
                .distinct()
            )
            .scalars()
            .all()
        )
        names = [n for n in names if n and n.strip()]
        print(f"Уникальных названий для эмбеддинга: {len(names)}")
        batch, done = 500, 0
        for i in range(0, len(names), batch):
            emb.embed_batch(db, names[i : i + batch])
            db.commit()
            done += len(names[i : i + batch])
            print(f"  ... {done}/{len(names)}", flush=True)
        print("Эмбеддинги позиций пред-прогреты")
    finally:
        db.close()


def rematch(args: list[str]) -> None:
    """Перепрогон каскада по всем активным позициям С ЗАПИСЬЮ в price_items.

    Так /stats и демо показывают реальное число, а не до-арбитражное. Печатает
    два честных числа: авто % от всех и от адресуемого знаменателя (всего минус
    позиции, по которым арбитр вынес «нет совпадения»). args[0] — лимит (dry-run).
    """
    from sqlalchemy import select

    from app.models import PriceItem
    from app.normalization import llm_arbiter
    from app.normalization.cascade import MatchCascade
    from app.normalization.match_service import apply_match

    limit = int(args[0]) if args else None
    db = SessionLocal()
    try:
        llm_arbiter.reset_usage()
        cascade = MatchCascade(db)  # лексический индекс строится один раз
        q = select(PriceItem).where(PriceItem.is_active.is_(True)).order_by(PriceItem.item_id)
        if limit:
            q = q.limit(limit)
        items = list(db.execute(q).scalars().all())
        total = len(items)
        auto = review = arbiter_no = unmatched = 0
        for i, item in enumerate(items, 1):
            oc = cascade.match(item.service_name_raw, item.category, item.service_code_source)
            apply_match(db, item, oc)
            if oc.is_auto:
                auto += 1
            elif oc.service_id is not None:
                review += 1
            elif oc.arbiter_no:
                arbiter_no += 1
            else:
                unmatched += 1
            if i % 200 == 0:
                db.commit()
                print(f"  ... {i}/{total} авто={auto} арбитр_нет={arbiter_no}", flush=True)
        db.commit()

        addressable = total - arbiter_no
        u = llm_arbiter.get_usage()
        pct_all = (auto / total * 100) if total else 0.0
        pct_addr = (auto / addressable * 100) if addressable else 0.0
        print("=== РЕМАТЧ ИТОГ ===")
        print(f"всего активных: {total}")
        print(f"АВТО по всем позициям: {auto} = {pct_all:.2f}%")
        print(f"адресуемый знаменатель (всего - арбитр_нет {arbiter_no}): {addressable}")
        print(f"АВТО по адресуемому: {auto}/{addressable} = {pct_addr:.2f}%")
        print(f"в ревью: {review} | неадресуемо (арбитр нет): {arbiter_no} | unmatched: {unmatched}")
        print(
            f"арбитр: вызовов {u['calls']}, токены вход {u['prompt_tokens']} "
            f"выход {u['completion_tokens']}"
        )
    finally:
        db.close()


def warm_arbiter(args: list[str]) -> None:
    """Конкурентный пред-прогрев кэша вердиктов арбитра по полосе [low, high).

    Пред-проход (без арбитра) собирает уникальные пограничные запросы, затем
    они запрашиваются у gpt-4o-mini в несколько потоков и кладутся в ai_cache.
    После этого rematch берёт вердикты из кэша и идёт быстро. args[0] — лимит.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from sqlalchemy import select

    from app.config import settings
    from app.models import AICache, PriceItem
    from app.normalization import llm_arbiter as arb
    from app.normalization.cascade import MatchCascade

    limit = int(args[0]) if args else None
    workers = int(os.getenv("WARM_WORKERS", "12"))
    db = SessionLocal()
    try:
        arb.reset_usage()
        cascade = MatchCascade(db)
        q = select(PriceItem).where(PriceItem.is_active.is_(True)).order_by(PriceItem.item_id)
        if limit:
            q = q.limit(limit)
        items = list(db.execute(q).scalars().all())

        # Пред-проход без арбитра: собрать уникальные пограничные запросы.
        todo: dict[str, tuple[str, str | None, list[str]]] = {}
        for item in items:
            oc = cascade.match(
                item.service_name_raw, item.category, item.service_code_source, use_arbiter=False
            )
            in_band = (
                oc.service_id is None
                and oc.candidates
                and settings.match_low_threshold <= oc.score < settings.match_high_threshold
            )
            if not in_band:
                continue
            cands = [c.service_name for c in oc.candidates[: settings.arbiter_candidates]]
            k = arb.cache_key(item.service_name_raw, cands)
            if k and k not in todo:
                todo[k] = (item.service_name_raw, item.category, cands)
        print(f"Уникальных пограничных запросов: {len(todo)}", flush=True)

        existing = set()
        if todo:
            existing = set(
                db.execute(
                    select(AICache.cache_key).where(AICache.cache_key.in_(list(todo)))
                ).scalars().all()
            )
        pending = {k: v for k, v in todo.items() if k not in existing}
        print(f"в кэше уже {len(existing)}, к запросу {len(pending)} в {workers} потоков", flush=True)

        def work(kv: tuple[str, tuple[str, str | None, list[str]]]):
            k, (query, cat, cands) = kv
            return k, arb.verdict_for(query, cat, cands)

        results: list[tuple[str, dict]] = []
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for k, v in (f.result() for f in as_completed([ex.submit(work, kv) for kv in pending.items()])):
                if v is not None:
                    results.append((k, v))
                done += 1
                if done % 250 == 0:
                    print(f"  ... {done}/{len(pending)}", flush=True)

        for k, v in results:
            db.add(AICache(kind="llm", cache_key=k, payload=v))
        db.commit()
        u = arb.get_usage()
        print(
            f"Прогрето вердиктов {len(results)} | арбитр вызовов {u['calls']} "
            f"токены вход {u['prompt_tokens']} выход {u['completion_tokens']}"
        )
    finally:
        db.close()


def accuracy_check(args: list[str]) -> None:
    """Точность авто-матчей по КОД-ИСТИНЕ (честная проверка ≥85%).

    На позициях, чей код тарификатора резолвится в РОВНО 1 услугу справочника
    (известная верная пара), гоним ТЕКСТОВЫЙ каскад с code=None и сверяем
    авто-выбор арбитра с код-истиной. Так измеряется точность арбитра, а не код-
    матча. args[0] — лимит проверенных позиций.
    """
    from sqlalchemy import select

    from app.models import MatchMethod, PriceItem
    from app.normalization.cascade import MatchCascade
    from app.normalization.normalize import normalize_code

    cap = int(args[0]) if args else None
    db = SessionLocal()
    try:
        cascade = MatchCascade(db)
        items = (
            db.execute(
                select(PriceItem).where(
                    PriceItem.is_active.is_(True),
                    PriceItem.service_code_source.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        checked = correct = 0
        sample: list[tuple[str, bool]] = []
        for item in items:
            nc = normalize_code(item.service_code_source)
            if not nc:
                continue
            hits = cascade.lexical.by_code(nc)
            if len(hits) != 1:
                continue  # код-истина только при однозначном коде
            truth = hits[0].service_id
            oc = cascade.match(item.service_name_raw, item.category, code=None)
            if oc.is_auto and oc.method == MatchMethod.llm:
                checked += 1
                ok = oc.service_id == truth
                correct += int(ok)
                if len(sample) < 15:
                    sample.append((item.service_name_raw.strip()[:48], ok))
                if cap and checked >= cap:
                    break
        if checked:
            print(
                f"Точность арбитр-авто по код-истине: {correct}/{checked} = "
                f"{correct / checked * 100:.1f}%"
            )
        else:
            print("Арбитр-авто на код-истинной выборке не найдено")
        for nm, ok in sample:
            print(("  OK  " if ok else "  X   ") + nm)
    finally:
        db.close()


COMMANDS = {
    "seed-reference": seed_reference,
    "ingest": ingest,
    "reembed": reembed,
    "embed-items": embed_items,
    "warm-arbiter": warm_arbiter,
    "rematch": rematch,
    "accuracy-check": accuracy_check,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Команды: " + ", ".join(COMMANDS))
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
