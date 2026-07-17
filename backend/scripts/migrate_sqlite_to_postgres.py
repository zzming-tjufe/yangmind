"""
把本地 SQLite（yangmind.db）迁到 PostgreSQL。

用法（在 backend 目录）：

  # 1) 先起 Docker Postgres
  docker compose -f ../docker-compose.yml up -d

  # 2) 安装依赖
  pip install -r requirements.txt

  # 3) 迁移（默认读 ./yangmind.db → 环境变量 DATABASE_URL / 默认本地 Docker）
  python scripts/migrate_sqlite_to_postgres.py

  # 可选参数
  python scripts/migrate_sqlite_to_postgres.py --sqlite ./yangmind.db --postgres postgresql+psycopg://yangmind:yangmind@127.0.0.1:5432/yangmind
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

# 保证可从 backend 根目录导入 app
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import Base, normalize_database_url  # noqa: E402
from app.models import admin_extra as _admin  # noqa: F401,E402
from app.models import cms as _cms  # noqa: F401,E402
from app.models import game as _game  # noqa: F401,E402
from app.models import match as _match  # noqa: F401,E402
from app.models import survey as _survey  # noqa: F401,E402
from app.models import user as _user  # noqa: F401,E402

# 按外键依赖排序；同层内顺序可调
TABLE_ORDER = [
    "users",
    "survey_instruments",
    "experiments",
    "page_configs",
    "content_blocks",
    "survey_items",
    "experiment_scenes",
    "invite_codes",
    "survey_responses",
    "game_sessions",
    "survey_answers",
    "personality_scores",
    "game_rounds",
    "account_events",
    "pvp_matches",
    "pvp_rounds",
]


def _serialize_cell(value):
    if isinstance(value, (datetime, date)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value
    # SQLite 里 JSON 有时是 str
    return value


def _copy_table(src: Engine, dst: Engine, table_name: str) -> int:
    table = Base.metadata.tables[table_name]
    with src.connect() as sconn, dst.begin() as dconn:
        rows = sconn.execute(select(table)).mappings().all()
        if not rows:
            return 0
        payload = [{k: _serialize_cell(v) for k, v in dict(row).items()} for row in rows]
        # 分批插入，保留原 id
        batch = 200
        for i in range(0, len(payload), batch):
            chunk = payload[i : i + batch]
            stmt = pg_insert(table).values(chunk)
            # 若目标已有同 id，跳过（可重复跑）
            update_cols = {c.name: getattr(stmt.excluded, c.name) for c in table.columns if c.name != "id"}
            stmt = stmt.on_conflict_do_update(index_elements=[table.c.id], set_=update_cols)
            dconn.execute(stmt)
        return len(payload)


def _reset_sequences(dst: Engine) -> None:
    with dst.begin() as conn:
        for table_name in TABLE_ORDER:
            if table_name not in Base.metadata.tables:
                continue
            table = Base.metadata.tables[table_name]
            if "id" not in table.c:
                continue
            conn.execute(
                text(
                    f"""
                    SELECT setval(
                      pg_get_serial_sequence(:table, 'id'),
                      COALESCE((SELECT MAX(id) FROM {table_name}), 1),
                      true
                    )
                    """
                ),
                {"table": table_name},
            )


def migrate(sqlite_url: str, postgres_url: str, *, wipe: bool) -> None:
    src = create_engine(sqlite_url)
    dst_url = normalize_database_url(postgres_url)
    dst = create_engine(dst_url, pool_pre_ping=True)

    # 确认源有表
    src_tables = set(inspect(src).get_table_names())
    print(f"SQLite tables: {sorted(src_tables)}")

    Base.metadata.create_all(bind=dst)

    if wipe:
        print("Wipe: truncating destination tables…")
        with dst.begin() as conn:
            for name in reversed(TABLE_ORDER):
                if name in Base.metadata.tables:
                    conn.execute(text(f'TRUNCATE TABLE "{name}" RESTART IDENTITY CASCADE'))

    total = 0
    for name in TABLE_ORDER:
        if name not in Base.metadata.tables:
            continue
        if name not in src_tables:
            print(f"  skip {name} (not in sqlite)")
            continue
        n = _copy_table(src, dst, name)
        total += n
        print(f"  {name}: {n} rows")

    _reset_sequences(dst)
    print(f"Done. Migrated {total} rows total.")
    print("Next: set DATABASE_URL to Postgres and restart uvicorn.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate YangMind SQLite → PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default=str(ROOT / "yangmind.db"),
        help="Path to SQLite file",
    )
    parser.add_argument(
        "--postgres",
        default=None,
        help="Postgres URL (default: env DATABASE_URL or local Docker)",
    )
    parser.add_argument(
        "--wipe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Truncate Postgres tables before copy (default: true)",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    from app.core.config import settings

    postgres = args.postgres or settings.database_url
    if postgres.startswith("sqlite"):
        postgres = "postgresql+psycopg://yangmind:yangmind@127.0.0.1:5432/yangmind"

    sqlite_url = f"sqlite:///{sqlite_path.resolve().as_posix()}"
    print(f"From: {sqlite_url}")
    print(f"To:   {normalize_database_url(postgres)}")
    migrate(sqlite_url, postgres, wipe=args.wipe)


if __name__ == "__main__":
    main()
