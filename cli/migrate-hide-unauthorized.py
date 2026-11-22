#!/usr/bin/env python3
"""一次性迁移：把存量普通用户（非管理员/超管）的 hide_unauthorized 默认设为 1。

- 精确条件：is_admin=0 AND is_super_admin=0 AND hide_unauthorized=0
- 幂等：重复执行第二次 affected=0
- 备份先行：迁移前把 skills.db 复制为 skills.db.bak-hide-<ts>（无论是否 dry-run 都只在 --apply 时备份）
- 用法：python migrate-hide-unauthorized.py [--db PATH] [--apply]
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / 'data' / 'skills.db'
WHERE = "is_admin=0 AND is_super_admin=0 AND hide_unauthorized=0 AND deleted_at IS NULL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', type=Path, default=DEFAULT_DB)
    ap.add_argument('--apply', action='store_true', help='真正写库；默认 dry-run')
    args = ap.parse_args()

    db = args.db.resolve()
    if not db.exists():
        print(f'ABORT: db not found: {db}')
        sys.exit(2)

    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    cols = {r[1] for r in conn.execute('PRAGMA table_info(users)')}
    need = {'is_admin', 'is_super_admin', 'hide_unauthorized'}
    if not need <= cols:
        print(f'ABORT: missing columns: {need - cols}')
        sys.exit(2)
    if 'deleted_at' not in cols:
        WHERE_SAFE = WHERE.replace(' AND deleted_at IS NULL', '')
    else:
        WHERE_SAFE = WHERE

    targets = conn.execute(f'SELECT id, username FROM users WHERE {WHERE_SAFE}').fetchall()
    print(f'DB: {db}')
    print(f'normal users to migrate: {len(targets)}')
    for row in targets:
        print(f'  - id={row[0]} {row[1]}')
    conn.close()

    if not args.apply:
        print('DRY-RUN only (pass --apply to write).')
        return
    if not targets:
        print('ALREADY MIGRATED / nothing to do.')
        return

    bak = db.with_name(f'skills.db.bak-hide-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}')
    shutil.copy2(db, bak)
    print(f'backup: {bak}')

    conn = sqlite3.connect(str(db))
    cur = conn.execute(f'UPDATE users SET hide_unauthorized=1 WHERE {WHERE_SAFE}')
    conn.commit()
    print(f'updated rows: {cur.rowcount}')
    conn.close()

    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    remaining = conn.execute(f'SELECT COUNT(*) FROM users WHERE {WHERE_SAFE}').fetchone()[0]
    conn.close()
    print(f'remaining to migrate: {remaining}')
    if remaining != 0:
        print('WARN: still has unmigrated rows')
        sys.exit(3)
    print('DONE')


if __name__ == '__main__':
    main()
