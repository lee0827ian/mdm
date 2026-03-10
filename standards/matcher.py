"""
StandardMatcher
RAW 품명을 표준품명 DB와 매핑.

매핑 전략 (우선순위 순):
1. 정확 매핑 (exact match)
2. 정규화 후 정확 매핑 (공백/특수문자 제거)
3. 포함 매핑 (표준품명이 RAW 안에 포함)
4. 토큰 교집합 (단어 단위 유사도)
5. fallback_similar: 실패 시 DB 내 유사 표준품명 강제 탐색
   5-1. PRODUCT_NAME_ALIAS 직접 매핑 (data/product_name_alias.py)
   5-2. KEYWORD_CATEGORY_HINTS 세분류 좁히기
   5-3. suffix 부분 문자열 + 재질 일관성 점수화
"""

import re
from typing import Optional
from standards.db_loader import StandardDBLoader
from data.product_name_alias import PRODUCT_NAME_ALIAS


# ── 핵심 키워드 → 표준품명 세분류 힌트 사전 ──────────────────────────────────
KEYWORD_CATEGORY_HINTS: dict[str, list[str]] = {
    '티슈':       ['물티슈', '화장지'],
    '물티슈':     ['물티슈'],
    '세정티슈':   ['물티슈', '전산크리너/청소용품'],
    '청소':       ['물티슈', '전산크리너/청소용품', '세탁세제/비누'],
    '엘라스토머': ['오링', '축실(OIL/LIP/SHAFT)', 'U/V실'],
    '오링':       ['오링'],
    # '링' 단독 힌트 제거 - '락', '링크' 등 노이즈 차단
    # '링' 포함 단어는 '엘라스토머링', '오링' 등 구체적 alias로 처리
    '씰':         ['오링', '축실(OIL/LIP/SHAFT)', 'U/V실'],
    '수건':       ['세면/샤워용품', '생활잡화'],
    '타월':       ['세면/샤워용품', '생활잡화'],
    '극세사':     ['세면/샤워용품'],
    '세차':       ['세면/샤워용품', '차량관리용품'],
    '케이블':     ['전선/케이블', '통신선로자재', '전기배선부품'],
    '브라켓':     ['배관지지대', '금속부품/브라켓'],
    '거치대':     ['배관지지대', '금속부품/브라켓', '사무용품'],
}

# 너무 일반적인 품명 패널티
GENERIC_NAME_PENALTY: set[str] = {
    # 단독으로는 너무 일반적인 표준품명 - contains로 잡혀도 확정 금지
    '링', '씰', '수건', '타월', '티슈', '패드', '세트',
    '모니터', '브라켓', '케이블', '센서', '밸브', '펌프',
    '모터', '스위치', '커넥터', '어댑터', '필터', '팬',
}


class MatchResult:
    __slots__ = ['matched', 'std_name', 'std_item', 'method', 'score', 'attrs']

    def __init__(self, matched: bool, std_name: str = '',
                 std_item: dict = None, method: str = '', score: float = 0.0):
        self.matched  = matched
        self.std_name = std_name
        self.std_item = std_item or {}
        self.method   = method
        self.score    = score
        self.attrs    = []

    def __repr__(self):
        return (f"MatchResult(matched={self.matched}, "
                f"std_name='{self.std_name}', "
                f"method='{self.method}', score={self.score:.2f})")


class StandardMatcher:
    """RAW 품명 → 표준품명 매핑 엔진"""

    MIN_SCORE        = 0.4
    FALLBACK_MIN     = 0.35  # 낮으면 엉뚱한 품명 확정됨
    AUTO_CONFIRM_GAP = 0.15

    def __init__(self, db_loader: StandardDBLoader):
        self.db = db_loader
        self._all_names = db_loader.get_all_names()
        self._normalized_map = self._build_normalized_map()
        self._category_index = self._build_category_index()

    def _build_normalized_map(self) -> dict[str, str]:
        result = {}
        for name in self._all_names:
            normalized = self._normalize(name)
            if normalized not in result:
                result[normalized] = name
        return result

    def _build_category_index(self) -> dict[str, list[str]]:
        index: dict[str, list[str]] = {}
        rows = self.db._conn.execute(
            "SELECT 품명, 세분류 FROM std_item"
        ).fetchall()
        for 품명, 세분류 in rows:
            if 세분류 not in index:
                index[세분류] = []
            index[세분류].append(품명)
        return index

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ''
        text = text.lower().strip()
        text = re.sub(r'[\s\-_/·•]', '', text)
        text = re.sub(r'[^\w가-힣]', '', text)
        return text

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = re.split(r'[\s\-_/,·•()\[\]]+', text.strip())
        return {t.lower() for t in tokens if len(t) >= 2}

    def match(self, raw_name: str) -> MatchResult:
        if not raw_name or not raw_name.strip():
            return MatchResult(False, method='empty')

        raw = raw_name.strip()

        # ── 1. 정확 매핑 ──────────────────────────────────────────────────
        item = self.db.get_item_by_name(raw)
        if item:
            return self._make_result(item, 'exact', 1.0)

        # ── 2. 정규화 매핑 ────────────────────────────────────────────────
        raw_norm = self._normalize(raw)
        if raw_norm and raw_norm in self._normalized_map:
            std_name = self._normalized_map[raw_norm]
            item = self.db.get_item_by_name(std_name)
            if item:
                return self._make_result(item, 'normalized', 0.95)

        # ── 3. 포함 매핑 ─────────────────────────────────────────────────
        best = self._match_contains(raw)
        if best and best.score >= self.MIN_SCORE:
            return best

        # ── 4. 토큰 교집합 매핑 ──────────────────────────────────────────
        best_token = self._match_token(raw)
        if best_token and best_token.score >= self.MIN_SCORE:
            return best_token

        return MatchResult(False, method='no_match', score=0.0)

    def find_best_similar_standard(
        self,
        raw_name: str,
        policy: str = '',
        parsed_spec: dict = None,
        top_k: int = 5,
    ) -> MatchResult:
        """
        매핑 실패 시 DB 내 유사 표준품명 강제 탐색.

        우선순위:
        1. PRODUCT_NAME_ALIAS 직접 매핑 (동의어/상위개념 사전)
        2. KEYWORD_CATEGORY_HINTS 세분류 좁히기 + 점수화
        3. 전체 DB 토큰 탐색 (최후 안전망)
        """
        if not raw_name:
            return MatchResult(False, method='fallback_empty')

        raw = raw_name.strip()
        parsed_spec = parsed_spec or {}

        # ── 1. PRODUCT_NAME_ALIAS 직접 매핑 ─────────────────────────────
        alias = PRODUCT_NAME_ALIAS.get(raw)
        if alias:
            item = self.db.get_item_by_name(alias)
            if item:
                return self._make_result(item, 'fallback_similar_confirmed', 0.85)

        # ── 2. 세분류 후보 좁히기 ────────────────────────────────────────
        candidate_names = self._get_category_candidates(raw)

        # 세분류 힌트 없으면 전체 탐색 금지 → 오매핑 방지
        # 카테고리를 특정할 수 없는 품명은 원본 유지가 더 안전
        if not candidate_names:
            return MatchResult(False, method='fallback_no_hint')

        # ── 3. 후보 점수화 ───────────────────────────────────────────────
        scored = self._score_candidates(raw, candidate_names, parsed_spec)

        if not scored:
            return MatchResult(False, method='fallback_no_candidate')

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        best_score, best_name = top[0]
        second_score = top[1][0] if len(top) > 1 else 0.0

        if best_score < self.FALLBACK_MIN:
            return MatchResult(False, method='fallback_low_score')

        item = self.db.get_item_by_name(best_name)
        if not item:
            return MatchResult(False, method='fallback_item_missing')

        result = self._make_result(item, 'fallback_similar', best_score)

        gap = best_score - second_score
        if gap >= self.AUTO_CONFIRM_GAP:
            result.method = 'fallback_similar_confirmed'
        else:
            result.method = 'fallback_similar_flagged'

        # flagged이고 점수가 낮으면 원본 유지가 더 안전
        if result.method == 'fallback_similar_flagged' and best_score < 0.45:
            return MatchResult(False, method='fallback_uncertain')

        return result

    def match_with_candidates(self, raw_name: str, top_n: int = 3) -> list[MatchResult]:
        if not raw_name:
            return []

        raw = raw_name.strip()
        candidates = []

        exact = self.match(raw)
        if exact.matched:
            candidates.append(exact)
            if len(candidates) >= top_n:
                return candidates

        raw_tokens = self._tokenize(raw)
        if not raw_tokens:
            return candidates

        scored = []
        for std_name in self._all_names:
            std_tokens = self._tokenize(std_name)
            if not std_tokens:
                continue
            intersection = raw_tokens & std_tokens
            if not intersection:
                continue
            score = len(intersection) / max(len(raw_tokens), len(std_tokens))
            if score >= self.MIN_SCORE:
                scored.append((score, std_name))

        scored.sort(reverse=True)
        for score, std_name in scored[:top_n]:
            if any(c.std_name == std_name for c in candidates):
                continue
            item = self.db.get_item_by_name(std_name)
            if item:
                candidates.append(self._make_result(item, 'token', score))

        return candidates[:top_n]

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────

    def _get_category_candidates(self, raw: str) -> list[str]:
        raw_lower = raw.lower()
        target_categories: set[str] = set()

        for keyword, categories in KEYWORD_CATEGORY_HINTS.items():
            if keyword in raw_lower:
                target_categories.update(categories)

        if not target_categories:
            return []

        candidates = []
        for cat in target_categories:
            candidates.extend(self._category_index.get(cat, []))
        return list(set(candidates))

    def _score_candidates(
        self,
        raw: str,
        candidates: list[str],
        parsed_spec: dict,
    ) -> list[tuple[float, str]]:
        raw_lower  = raw.lower()
        raw_tokens = self._tokenize(raw)
        scored     = []

        material  = (parsed_spec.get('material') or '').lower()
        spec_text = ' '.join(str(v) for v in parsed_spec.values()).lower()
        rubber_kw = {'pu', 'nbr', 'epdm', 'viton', '고무', '실리콘', '엘라스토머'}

        for std_name in candidates:
            score     = 0.0
            std_lower = std_name.lower()
            std_tokens = self._tokenize(std_name)

            # 토큰 교집합
            if raw_tokens and std_tokens:
                inter = raw_tokens & std_tokens
                if inter:
                    score += len(inter) / max(len(raw_tokens), len(std_tokens)) * 0.6

            # 포함 관계
            if std_lower in raw_lower:
                score += len(std_lower) / max(len(raw_lower), 1) * 0.4
            elif raw_lower in std_lower:
                score += len(raw_lower) / max(len(std_lower), 1) * 0.2

            # suffix 부분 문자열 매칭
            # 예: '혁명티슈' 끝 '티슈'(2글자)가 '물티슈'에 포함 → 점수 가산
            for length in range(2, min(len(raw_lower), len(std_lower)) + 1):
                suffix = raw_lower[-length:]
                if suffix in std_lower:
                    score += length / max(len(std_lower), 1) * 0.25
                    break

            # 재질 일관성 가산 (고무/PU → 오링/링/씰류)
            if any(kw in spec_text for kw in rubber_kw):
                if any(kw in std_lower for kw in ['오링', '링', '씰', '고무']):
                    score += 0.15

            # spec 텍스트 토큰 가산
            # 예: spec에 '극세사' 있으면 '극세사수건' 점수 올림
            spec_tokens = self._tokenize(' '.join(str(v) for v in parsed_spec.values()))
            for tok in spec_tokens:
                if len(tok) >= 2 and tok in std_lower:
                    score += 0.2
                    break

            # 일반명 패널티
            if std_name in GENERIC_NAME_PENALTY:
                score -= 0.15

            if score > 0:
                scored.append((score, std_name))

        return scored

    def _match_contains(self, raw: str) -> Optional[MatchResult]:
        raw_lower  = raw.lower()
        best_name  = ''
        best_score = 0.0

        for std_name in self._all_names:
            # 1글자 한글 / 2글자 이하 영문 후보는 노이즈 차단
            if len(std_name) < 2:
                continue
            if len(std_name) <= 2 and std_name.isascii():
                continue
            if std_name.lower() in raw_lower:
                score = len(std_name) / max(len(raw), 1)
                if score > best_score:
                    best_score = score
                    best_name  = std_name

        if best_name:
            # 일반명에 contains로 걸리면 확정하지 않고 None 반환
            # → fallback_similar에서 spec 정보 포함해 재평가
            if best_name in GENERIC_NAME_PENALTY:
                return None
            item = self.db.get_item_by_name(best_name)
            return self._make_result(item, 'contains', min(best_score + 0.3, 0.9))
        return None

    def _match_token(self, raw: str) -> Optional[MatchResult]:
        raw_tokens = self._tokenize(raw)
        if not raw_tokens:
            return None

        best_name  = ''
        best_score = 0.0

        for std_name in self._all_names:
            std_tokens = self._tokenize(std_name)
            if not std_tokens:
                continue
            intersection = raw_tokens & std_tokens
            if not intersection:
                continue
            score = len(intersection) / max(len(raw_tokens), len(std_tokens))
            if score > best_score:
                best_score = score
                best_name  = std_name

        if best_name:
            item = self.db.get_item_by_name(best_name)
            return self._make_result(item, 'token', best_score)
        return None

    def _make_result(self, item: dict, method: str, score: float) -> MatchResult:
        result = MatchResult(
            matched  = True,
            std_name = item['품명'],
            std_item = item,
            method   = method,
            score    = score,
        )
        result.attrs = self.db.get_attrs(item['id'])
        return result
