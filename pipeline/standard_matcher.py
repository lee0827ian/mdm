"""
[9] StandardMatcher (파이프라인 연결)
- RAW 품명 → 표준품명 DB 매핑
- normalize_product_name() 전처리 후 StandardMatcher 매핑
- 매핑 실패 시 find_best_similar_standard() fallback 탐색
- MatchResult → ResolvedField 변환
"""

from models.resolved_field import ResolvedField
from models.evidence import Evidence
from standards.db_loader import StandardDBLoader
from standards.matcher import StandardMatcher as CoreMatcher
from data.product_name_map import normalize_product_name

# fallback_similar_flagged 시 부착할 플래그 힌트
FLAG_SIMILAR_MATCH = 'FLAG_STD_SIMILAR_MATCH'


class StandardMatcherStep:
    """파이프라인 연결용 래퍼."""

    def __init__(self, db_loader: StandardDBLoader):
        self.db = db_loader
        self._core = CoreMatcher(db_loader)

    def match(self, name_field: ResolvedField, ev: Evidence,
              policy: str = '') -> ResolvedField:
        """
        표준품명 ResolvedField를 받아 DB 매핑 후 갱신된 ResolvedField 반환.

        흐름:
          1. normalize_product_name() → 영문→한글 전처리
          2. CoreMatcher.match()      → 1~4단계 매핑
          3. 슬래시 복합 품명 토큰 매핑
          4. 매핑 실패 시 find_best_similar_standard() fallback
          5. ResolvedField 반환 (플래그 힌트 포함)
        """
        raw = name_field.value
        if not raw:
            return name_field

        # ── Step 1. 영문 → 한글 전처리 ───────────────────────────────────
        preprocessed = normalize_product_name(raw)

        # ── Step 2. 일반 DB 매핑 ─────────────────────────────────────────
        result = self._core.match(preprocessed)

        if not result.matched and preprocessed != raw:
            result = self._core.match(raw)

        # ── Step 3. 슬래시 복합 품명 토큰 매핑 ──────────────────────────
        if not result.matched or result.method == 'contains':
            token_result = self._match_slash_tokens(preprocessed or raw)
            if token_result and token_result.matched:
                if not result.matched or token_result.score >= result.score:
                    result = token_result

        # ── Step 4. fallback 유사 매핑 ───────────────────────────────────
        if not result.matched:
            # spec 원문을 parsed_spec에 'raw_spec' 키로 추가해 점수화에 활용
            parsed_spec = dict(ev.parsed_spec or {})
            raw_spec = ' '.join(f for f, _ in (ev.spec_fragments or []))
            if raw_spec:
                parsed_spec['raw_spec'] = raw_spec
            result = self._core.find_best_similar_standard(
                raw_name    = preprocessed or raw,
                policy      = policy,
                parsed_spec = parsed_spec,
            )

        # ── Step 5. 결과 반환 ────────────────────────────────────────────
        if result.matched:
            # fallback_similar_flagged → 플래그 힌트 추가
            extra_flag = ''
            if result.method == 'fallback_similar_flagged':
                extra_flag = f' | {FLAG_SIMILAR_MATCH}'

            return ResolvedField(
                value      = result.std_name,
                source     = name_field.source,
                confidence = self._score_to_confidence(result.score),
                rationale  = (
                    f"DB매핑 [{result.method}] "
                    f"score={result.score:.2f} | "
                    f"원본='{raw}' → 전처리='{preprocessed}' → 표준='{result.std_name}' | "
                    f"분류={result.std_item.get('대분류','')}/"
                    f"{result.std_item.get('세분류','')} | "
                    f"속성 {len(result.attrs)}개{extra_flag}"
                ),
                std_item   = result.std_item,
                attrs      = result.attrs,
            )

        # 최종 실패
        return ResolvedField(
            value      = preprocessed or raw,
            source     = name_field.source,
            confidence = 'low',
            rationale  = (
                f"DB매핑 실패 | 원본='{raw}' | "
                f"전처리='{preprocessed}' | FLAG_STD_UNMATCHED"
            ),
            std_item   = {},
            attrs      = [],
        )

    def _match_slash_tokens(self, name: str):
        """슬래시 복합 품명 토큰 조합 매핑."""
        if '/' not in name:
            return None

        import re
        tokens = [t.strip() for t in re.split(r'[/／]', name) if t.strip()]
        if len(tokens) < 2:
            return None

        best = None
        best_score = 0.0

        for std_name in self._core._all_names:
            std_lower = std_name.lower()
            if all(t.lower() in std_lower for t in tokens):
                score = sum(len(t) for t in tokens) / max(len(std_name), 1)
                score = min(score + 0.2, 0.95)
                if score > best_score:
                    best_score = score
                    best = std_name

        if best:
            item = self._core.db.get_item_by_name(best)
            if item:
                return self._core._make_result(item, 'slash_token', best_score)

        return None

    def match_candidates(self, raw_name: str, top_n: int = 3) -> list:
        """수동검토용 후보 목록 반환"""
        preprocessed = normalize_product_name(raw_name)
        return self._core.match_with_candidates(preprocessed, top_n=top_n)

    @staticmethod
    def _score_to_confidence(score: float) -> str:
        if score >= 0.85:
            return 'high'
        if score >= 0.5:
            return 'medium'
        return 'low'