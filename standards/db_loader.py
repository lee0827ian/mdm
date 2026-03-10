"""
StandardDBLoader
standards.db에서 표준품명/속성 정의를 조회하는 인터페이스.
파이프라인 시작 시 한 번 로딩 후 재사용.
"""

import sqlite3
from pathlib import Path
from functools import lru_cache
from typing import Optional

DB_PATH = Path(__file__).parent / 'standards.db'


class StandardDBLoader:
    """표준 DB 조회 인터페이스"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # 품명 전체 캐시 (매핑용)
        self._item_cache: dict[str, dict] = {}
        self._load_item_cache()

    def _load_item_cache(self):
        """품명 전체를 메모리에 로딩 (47,991개 - 빠른 매핑용)"""
        rows = self._conn.execute("""
            SELECT id, 품명, 영문명, 품목코드, 분류코드,
                   대분류, 중분류, 소분류, 세분류
            FROM std_item
        """).fetchall()

        for row in rows:
            self._item_cache[row['품명']] = dict(row)

        print(f"[StandardDBLoader] 품명 {len(self._item_cache):,}개 캐시 완료")

    # -------------------------------------------------------------------------
    # 품명 조회
    # -------------------------------------------------------------------------

    def get_item_by_name(self, 품명: str) -> Optional[dict]:
        """정확한 품명으로 조회"""
        return self._item_cache.get(품명.strip())

    def get_all_names(self) -> list[str]:
        """전체 표준품명 목록 반환"""
        return list(self._item_cache.keys())

    def get_item_by_code(self, 품목코드: str) -> Optional[dict]:
        """품목코드로 조회"""
        row = self._conn.execute(
            "SELECT * FROM std_item WHERE 품목코드 = ?", (품목코드,)
        ).fetchone()
        return dict(row) if row else None

    def search_by_category(self, 대분류: str = None, 중분류: str = None,
                           소분류: str = None) -> list[dict]:
        """분류로 품명 목록 조회"""
        conditions = []
        params = []
        if 대분류:
            conditions.append("대분류 = ?")
            params.append(대분류)
        if 중분류:
            conditions.append("중분류 = ?")
            params.append(중분류)
        if 소분류:
            conditions.append("소분류 = ?")
            params.append(소분류)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._conn.execute(
            f"SELECT * FROM std_item {where}", params
        ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 속성 조회
    # -------------------------------------------------------------------------

    def get_attrs(self, 품명id: int) -> list[dict]:
        """품명id로 속성 정의 조회"""
        rows = self._conn.execute("""
            SELECT 속성순서, 속성명
            FROM std_item_attr
            WHERE 품명id = ?
            ORDER BY 속성순서
        """, (품명id,)).fetchall()
        return [dict(r) for r in rows]

    def get_attrs_by_name(self, 품명: str) -> list[dict]:
        """품명으로 속성 정의 조회"""
        item = self.get_item_by_name(품명)
        if not item:
            return []
        return self.get_attrs(item['id'])

    def get_required_attrs(self, 품명: str) -> list[str]:
        """품명의 필수 속성명 목록 반환 (비고 제외)"""
        attrs = self.get_attrs_by_name(품명)
        # '비고'는 선택 속성으로 처리
        return [a['속성명'] for a in attrs if a['속성명'] not in ('비고', '')]

    # -------------------------------------------------------------------------
    # 통계/유틸
    # -------------------------------------------------------------------------

    def get_categories(self) -> dict:
        """대/중/소분류 목록 조회"""
        rows = self._conn.execute("""
            SELECT DISTINCT 대분류, 중분류, 소분류
            FROM std_item
            ORDER BY 대분류, 중분류, 소분류
        """).fetchall()
        result = {}
        for row in rows:
            대 = row['대분류'] or '미분류'
            중 = row['중분류'] or '미분류'
            소 = row['소분류'] or '미분류'
            result.setdefault(대, {}).setdefault(중, set()).add(소)
        return result

    def close(self):
        self._conn.close()