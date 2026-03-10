"""
표준 기준 데이터 → SQLite 임포트 스크립트
실행: python standards/import_standards.py

파일 규칙:
  품명_분류_속성.xlsx  (또는 .csv)  → std_item + std_item_attr
  제조사*.xlsx         (또는 .csv)  → std_maker
  단위*.xlsx           (또는 .csv)  → std_unit
"""

import sqlite3
import pandas as pd
import sys
from pathlib import Path

DB_PATH       = Path(__file__).parent / 'standards.db'
STANDARDS_DIR = Path(__file__).parent


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS std_item (
            id           INTEGER PRIMARY KEY,
            no           INTEGER,
            품명         TEXT NOT NULL,
            영문명       TEXT,
            품목코드     TEXT,
            분류코드     TEXT,
            대분류       TEXT,
            중분류       TEXT,
            소분류       TEXT,
            세분류       TEXT
        );
        CREATE TABLE IF NOT EXISTS std_item_attr (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            품명id       INTEGER NOT NULL,
            속성순서     INTEGER NOT NULL,
            속성명       TEXT NOT NULL,
            FOREIGN KEY (품명id) REFERENCES std_item(id)
        );
        CREATE TABLE IF NOT EXISTS std_maker (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            표준제조사명     TEXT NOT NULL,
            영문명           TEXT,
            제조사코드       TEXT,
            취급품목         TEXT,
            홈페이지         TEXT,
            소싱그룹사용여부 TEXT,
            비고             TEXT
        );
        CREATE TABLE IF NOT EXISTS std_unit (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            품명id       INTEGER,
            품목코드     TEXT,
            허용단위     TEXT NOT NULL,
            단위원명     TEXT,
            단위코드     TEXT,
            기본단위     TEXT,
            비고         TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_item_품명     ON std_item(품명);
        CREATE INDEX IF NOT EXISTS idx_item_품목코드 ON std_item(품목코드);
        CREATE INDEX IF NOT EXISTS idx_item_분류코드 ON std_item(분류코드);
        CREATE INDEX IF NOT EXISTS idx_attr_품명id   ON std_item_attr(품명id);
        CREATE INDEX IF NOT EXISTS idx_maker_name    ON std_maker(표준제조사명);
        CREATE INDEX IF NOT EXISTS idx_maker_code    ON std_maker(제조사코드);
    """)
    conn.commit()
    print("✅ DB 테이블 생성 완료")


def load_file(filepath: Path) -> pd.DataFrame:
    if filepath.suffix.lower() == '.csv':
        for enc in ('utf-8-sig', 'utf-8', 'euc-kr', 'cp949'):
            try:
                df = pd.read_csv(filepath, dtype=str, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
    else:
        try:
            df = pd.read_excel(filepath, dtype=str, engine='calamine')
        except Exception:
            df = pd.read_excel(filepath, dtype=str, engine='openpyxl')
    df = df.fillna('').astype(str).replace('nan', '').replace('None', '')
    df.columns = [str(c).strip() for c in df.columns]
    return df


def import_items(conn, filepath: Path):
    print(f"\n📂 파일 로딩: {filepath.name}")
    df = load_file(filepath)
    print(f"  총 {len(df)}행 로드")

    attr_cols = []
    for i in range(1, 12):
        for possible in [f'속성값{i}', f'속성값 {i}', f'attr{i}']:
            if possible in df.columns:
                attr_cols.append((i, possible))
                break
    print(f"  속성 컬럼 감지: {[c for _, c in attr_cols]}")

    conn.execute("DELETE FROM std_item_attr")
    conn.execute("DELETE FROM std_item")
    conn.commit()

    item_rows = []
    attr_rows = []
    for idx, row in df.iterrows():
        품명 = row.get('품명', '').strip()
        if not 품명 or 품명 in ('nan', 'None', ''):
            continue
        try:
            no = int(float(row.get('No', idx + 1)))
        except Exception:
            no = idx + 1
        item_id = no
        item_rows.append((
            item_id, no, 품명,
            row.get('영문명', '').strip(),
            row.get('품목코드', '').strip(),
            row.get('분류코드', '').strip(),
            row.get('대분류', '').strip(),
            row.get('중분류', '').strip(),
            row.get('소분류', '').strip(),
            row.get('세분류', '').strip(),
        ))
        for 순서, col in attr_cols:
            val = row.get(col, '').strip()
            if val and val not in ('nan', 'None', ''):
                attr_rows.append((item_id, 순서, val))

    conn.executemany("""
        INSERT OR REPLACE INTO std_item
        (id, no, 품명, 영문명, 품목코드, 분류코드, 대분류, 중분류, 소분류, 세분류)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, item_rows)
    conn.executemany("""
        INSERT INTO std_item_attr (품명id, 속성순서, 속성명)
        VALUES (?, ?, ?)
    """, attr_rows)
    conn.commit()
    print(f"  ✅ 품명 {len(item_rows)}개 임포트 완료")
    print(f"  ✅ 속성 정의 {len(attr_rows)}개 임포트 완료")


def import_makers(conn, filepath: Path):
    """컬럼: No, 제조사명, 영문, 제조사코드, 취급품목, 홈페이지, 소싱그룹사용여부, 제조사구분(무시)"""
    print(f"\n📂 제조사 파일 로딩: {filepath.name}")
    df = load_file(filepath)
    print(f"  총 {len(df)}행 로드")

    conn.execute("DELETE FROM std_maker")
    rows = []
    for _, row in df.iterrows():
        name = row.get('제조사명', '').strip()
        if not name or name in ('nan', 'None', ''):
            continue
        rows.append((
            name,
            row.get('영문', '').strip(),
            row.get('제조사코드', '').strip(),
            row.get('취급품목', '').strip(),
            row.get('홈페이지', '').strip(),
            row.get('소싱그룹사용여부', '').strip(),
            row.get('비고', '').strip(),  # ← 수정: No → 비고
        ))
    conn.executemany("""
        INSERT INTO std_maker
        (표준제조사명, 영문명, 제조사코드, 취급품목, 홈페이지, 소싱그룹사용여부, 비고)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"  ✅ 제조사 {len(rows)}개 임포트 완료")


def import_units(conn, filepath: Path):
    """컬럼: No, 단위, 단위원명, 단위구분(무시), 단위코드"""
    print(f"\n📂 단위 파일 로딩: {filepath.name}")
    df = load_file(filepath)
    print(f"  총 {len(df)}행 로드")

    conn.execute("DELETE FROM std_unit")
    rows = []
    for _, row in df.iterrows():
        허용단위 = (row.get('허용단위') or row.get('단위') or '').strip()
        if not 허용단위:
            continue
        rows.append((
            None,
            row.get('품목코드', '').strip(),
            허용단위,
            row.get('단위원명', '').strip(),
            row.get('단위코드', '').strip(),
            row.get('기본단위', '').strip(),
            row.get('비고', '').strip(),
        ))
    conn.executemany("""
        INSERT INTO std_unit (품명id, 품목코드, 허용단위, 단위원명, 단위코드, 기본단위, 비고)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"  ✅ 단위 규칙 {len(rows)}개 임포트 완료")


def verify_db(conn):
    print("\n📊 DB 검증")
    counts = {
        '표준품명': conn.execute("SELECT COUNT(*) FROM std_item").fetchone()[0],
        '속성정의': conn.execute("SELECT COUNT(*) FROM std_item_attr").fetchone()[0],
        '제조사':   conn.execute("SELECT COUNT(*) FROM std_maker").fetchone()[0],
        '단위규칙': conn.execute("SELECT COUNT(*) FROM std_unit").fetchone()[0],
    }
    for k, v in counts.items():
        print(f"  {k}: {v:,}건")

    print("\n  [샘플 - 표준품명]")
    for row in conn.execute("SELECT 품명, 대분류, 소분류 FROM std_item LIMIT 5"):
        print(f"    {row[0]} | {row[1]} | {row[2]}")

    if counts['단위규칙'] > 0:
        print("\n  [샘플 - 단위]")
        for row in conn.execute(
            "SELECT 허용단위, 단위원명, 단위코드 FROM std_unit LIMIT 5"
        ):
            print(f"    {row[0]} | {row[1]} | {row[2]}")

    if counts['제조사'] > 0:
        print("\n  [샘플 - 제조사]")
        for row in conn.execute(
            "SELECT 표준제조사명, 영문명, 취급품목 FROM std_maker LIMIT 5"
        ):
            print(f"    {row[0]} | {row[1]} | {row[2]}")


def main():
    print("=" * 50)
    print("MDM 표준 DB 임포트 시작")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    all_files = [f for f in STANDARDS_DIR.glob('*.*')
                 if not f.name.startswith('~$')
                 and f.suffix.lower() in ('.xlsx', '.xls', '.csv')]

    item_file  = next((f for f in all_files if '품명' in f.name), None)
    maker_file = next((f for f in all_files if '제조사' in f.name), None)
    unit_file  = next((f for f in all_files if '단위' in f.name), None)

    if item_file:
        import_items(conn, item_file)
    else:
        print("\n❌ 품명 파일 없음 (파일명에 '품명' 포함 필요)")
        sys.exit(1)

    if maker_file:
        import_makers(conn, maker_file)
    else:
        print("\n⚠️  제조사 파일 없음 → 파일명에 '제조사' 포함해서 넣고 재실행")

    if unit_file:
        import_units(conn, unit_file)
    else:
        print("⚠️  단위 파일 없음 → 파일명에 '단위' 포함해서 넣고 재실행")

    verify_db(conn)
    conn.close()
    print(f"\n✅ 완료: {DB_PATH}")


if __name__ == '__main__':
    main()