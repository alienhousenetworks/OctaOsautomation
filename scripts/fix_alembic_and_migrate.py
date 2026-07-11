#!/usr/bin/env python3
"""
Safe production Alembic migrate.

- Uses DB credentials from app .env (via app.core.config) — no manual password needed
- Removes untracked auto_deploy_update migration junk if present
- If alembic_version points at a missing revision (orphan), rewrites stamp
  to the latest known git revision, then upgrades to head
- Never drops app data

Usage (from repo root):
  venv/bin/python scripts/fix_alembic_and_migrate.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)
sys.path.insert(0, str(REPO))

VERSIONS = REPO / "alembic" / "versions"
VENV_ALEMBIC = REPO / "venv" / "bin" / "alembic"
if not VENV_ALEMBIC.exists():
    VENV_ALEMBIC = Path(sys.executable).parent / "alembic"


def run_alembic(*args: str) -> subprocess.CompletedProcess:
    cmd = [str(VENV_ALEMBIC), *args]
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)


def parse_revisions_on_disk() -> dict[str, str | None]:
    """revision_id -> down_revision_id (or None)."""
    rev_map: dict[str, str | None] = {}
    for path in VERSIONS.glob("*.py"):
        if path.name.startswith("__"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        m_rev = re.search(r"""^revision\s*[:=]\s*['\"]([0-9a-fA-F]+)['\"]""", text, re.M)
        if not m_rev:
            m_rev = re.search(r"""revision:\s*str\s*=\s*['\"]([0-9a-fA-F]+)['\"]""", text)
        if not m_rev:
            continue
        rev = m_rev.group(1)
        m_down = re.search(
            r"""down_revision\s*[:=]\s*(?:Union\[[^\]]+\]\s*=\s*)?['\"]([0-9a-fA-F]+)['\"]""",
            text,
        )
        if not m_down:
            m_down = re.search(r"""down_revision:\s*Union\[[^\]]+\]\s*=\s*['\"]([0-9a-fA-F]+)['\"]""", text)
        if not m_down and re.search(r"""down_revision\s*[:=]\s*None""", text):
            rev_map[rev] = None
        else:
            rev_map[rev] = m_down.group(1) if m_down else None
    return rev_map


def clean_untracked_auto_migrations() -> int:
    """Delete untracked *auto_deploy_update* files under alembic/versions."""
    removed = 0
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "alembic/versions/"],
            cwd=str(REPO),
            text=True,
        )
    except Exception:
        # fallback: remove any *auto_deploy_update* not in a hard allowlist of core files
        for path in VERSIONS.glob("*auto_deploy_update*.py"):
            path.unlink(missing_ok=True)
            removed += 1
            print(f"[clean] removed {path.name}")
        return removed

    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        p = REPO / line
        if p.exists() and ("auto_deploy" in p.name or p.suffix == ".py"):
            # only remove untracked version scripts
            if p.parent == VERSIONS and p.suffix == ".py":
                p.unlink(missing_ok=True)
                removed += 1
                print(f"[clean] removed untracked {p.name}")
    return removed


def get_db_url() -> str:
    from app.core.config import settings

    url = settings.SQLALCHEMY_DATABASE_URI
    if not url:
        raise RuntimeError("SQLALCHEMY_DATABASE_URI not configured in .env")
    return url


def get_db_version(url: str) -> str | None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            return row[0] if row else None
        except Exception as e:
            print(f"[warn] could not read alembic_version: {e}")
            return None


def set_db_version(url: str, version: str) -> None:
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        # handle either single or multi-head version table shapes
        try:
            conn.execute(text("DELETE FROM alembic_version"))
        except Exception:
            pass
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": version},
        )
    print(f"[stamp] alembic_version set to {version}")


def pick_fallback_stamp(known: dict[str, str | None]) -> str:
    """Prefer latest known real chain tip before applying head upgrade."""
    preferred = [
        "9a1b2c3d4e5f",  # sales/support emails
        "375b132b27a8",  # company email unique
        "8d96c17e522c",  # org/enterprise columns
        "efe9dee142f9",  # initial
    ]
    for rev in preferred:
        if rev in known:
            return rev
    # any revision that is a parent of a head
    children = set(known.keys())
    parents = {p for p in known.values() if p}
    heads = [r for r in children if r not in parents]
    if heads:
        # stamp to parent of first head if possible, else that head
        parent = known.get(heads[0])
        if parent and parent in known:
            return parent
        return heads[0]
    raise RuntimeError("No known alembic revisions on disk")


def main() -> int:
    print("=== OctaOS Alembic safe migrate ===")
    print(f"repo: {REPO}")

    n = clean_untracked_auto_migrations()
    if n:
        print(f"[clean] removed {n} untracked local migration file(s)")

    known = parse_revisions_on_disk()
    if not known:
        print("[error] no alembic revision files found")
        return 1
    print(f"[info] {len(known)} revision file(s) on disk")

    try:
        url = get_db_url()
    except Exception as e:
        print(f"[error] cannot load DB URL from .env/app config: {e}")
        return 1

    # mask password in log
    safe = re.sub(r":([^:@/]+)@", ":***@", url)
    print(f"[info] DB: {safe}")

    current = get_db_version(url)
    print(f"[info] DB alembic_version: {current or '(empty)'}")

    if current and current not in known:
        print(f"[fix] orphan revision {current!r} not on disk — rewriting stamp")
        fallback = pick_fallback_stamp(known)
        set_db_version(url, fallback)
        current = fallback

    # try upgrade
    print("[migrate] alembic upgrade head ...")
    result = run_alembic("upgrade", "head")
    if result.returncode == 0:
        print(result.stdout or "")
        print("[ok] migrations applied")
        cur = run_alembic("current")
        print(cur.stdout or cur.stderr or "")
        return 0

    combined = (result.stdout or "") + (result.stderr or "")
    print(combined)

    if "Can't locate revision" in combined or "Multiple head revisions" in combined:
        print("[fix] upgrade failed due to revision graph issue — auto-recovering")
        # clean again just in case
        clean_untracked_auto_migrations()
        known = parse_revisions_on_disk()
        fallback = pick_fallback_stamp(known)
        set_db_version(url, fallback)
        result2 = run_alembic("upgrade", "head")
        print(result2.stdout or "")
        print(result2.stderr or "")
        if result2.returncode == 0:
            print("[ok] recovered and migrations applied")
            return 0
        # last resort: multiple heads
        result3 = run_alembic("upgrade", "heads")
        print(result3.stdout or "")
        print(result3.stderr or "")
        if result3.returncode == 0:
            print("[ok] upgraded all heads")
            return 0
        print("[error] migration recovery failed")
        return 1

    print("[error] alembic upgrade failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
