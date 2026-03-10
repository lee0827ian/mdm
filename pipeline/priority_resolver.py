"""
[4] SourcePriorityResolver
- 여러 후보 중 우선순위에 따라 최종값 결정
- 모델명 / 제조사 / 규격 각각 우선순위 적용

v1.1 변경:
  - resolve_model(): current/first_info가 있으면 memo_override는 후보 추가만,
    최종 확정값은 current/first_info 우선
    → FLAG_MEMO_OVERRIDE는 유지 (사람이 메모 내용 확인 가능)
"""

from models.evidence import Evidence
from models.resolved_field import ResolvedField
from config import MODEL_PRIORITY, MAKER_PRIORITY
from utils.text_utils import clean_value, simplify_company_name
from data.policy_rules import SIJUNGPUM_EXCEPTION_KEYWORDS


class SourcePriorityResolver:

    def resolve_model(self, ev: Evidence) -> ResolvedField:
        """
        모델명 우선순위 적용

        v1.1 규칙:
          - current / first_info 가 있으면 → 해당값 확정, memo_override는 무시
          - current / first_info 가 없으면 → memo_override 사용
          - FLAG_MEMO_OVERRIDE는 memo가 있을 때 항상 부착 (사람이 검토)
        """
        candidates = ev.model_candidates

        if not candidates:
            return ResolvedField(
                value='',
                source='fallback',
                confidence='low',
                rationale='모델명 후보 없음',
            )

        # 후보를 소스별로 분리
        memo_candidates    = [(v, s) for v, s in candidates if s == 'memo_override']
        current_candidates = [(v, s) for v, s in candidates if s == 'current']
        first_candidates   = [(v, s) for v, s in candidates if s == 'first_info']
        other_candidates   = [(v, s) for v, s in candidates
                              if s not in ('memo_override', 'current', 'first_info')]

        has_memo    = bool(memo_candidates)
        has_current = bool(current_candidates)
        has_first   = bool(first_candidates)

        # ── 결정 로직 ────────────────────────────────────────────────────────
        # current 또는 first_info가 있으면 memo_override는 확정 불가
        if has_current or has_first:
            # current 우선, 없으면 first_info
            if has_current:
                best_val, best_source = current_candidates[0]
                rationale = f'current 값 우선 확정 (memo_override 무시)'
            else:
                best_val, best_source = first_candidates[0]
                rationale = f'first_info 값 우선 확정 (memo_override 무시)'

            if has_memo:
                memo_val = memo_candidates[0][0]
                rationale += f' | 메모 제안값: {memo_val!r} → FLAG_MEMO_OVERRIDE 참조'

        elif has_memo:
            # current/first_info 없을 때만 memo_override 사용
            best_val, best_source = memo_candidates[0]
            rationale = 'current/first_info 없음 → memo_override 채택'

        else:
            # 나머지 우선순위 적용
            sorted_other = sorted(
                other_candidates,
                key=lambda x: MODEL_PRIORITY.get(x[1], 99)
            )
            if not sorted_other:
                return ResolvedField(
                    value='',
                    source='fallback',
                    confidence='low',
                    rationale='유효한 모델명 후보 없음',
                )
            best_val, best_source = sorted_other[0]
            rationale = f'모델명 후보 {len(other_candidates)}개 중 {best_source} 우선 선택'

        confidence = self._source_to_confidence(best_source)

        return ResolvedField(
            value=best_val,
            source=best_source,
            confidence=confidence,
            rationale=rationale,
        )

    def resolve_maker(self, ev: Evidence, policy: str) -> ResolvedField:
        """
        제조사 우선순위 적용
        수정메모 > 현재값 > 최초값 > spec추출 > URL > 텍스트 > FactFinder > 시중품
        """
        candidates = ev.maker_candidates

        # 볼트/너트 시중품 예외 처리
        if self._is_sijungpum_exception(ev):
            return ResolvedField(
                value='시중품',
                source='rule',
                confidence='high',
                rationale='볼트/너트류 규격품 → 시중품 처리',
            )

        if not candidates:
            return ResolvedField(
                value='시중품',
                source='sijungpum',
                confidence='low',
                rationale='제조사 후보 없음 → 시중품',
            )

        # placeholder 제거
        valid = [(v, s) for v, s in candidates if v and v not in ('--', '-', '시중품')]
        if not valid:
            return ResolvedField(
                value='시중품',
                source='sijungpum',
                confidence='low',
                rationale='유효한 제조사 후보 없음 → 시중품',
            )

        # 우선순위 정렬
        sorted_candidates = sorted(
            valid,
            key=lambda x: MAKER_PRIORITY.get(x[1], 99)
        )

        best_val, best_source = sorted_candidates[0]
        confidence = self._source_to_confidence(best_source)

        return ResolvedField(
            value=best_val,
            source=best_source,
            confidence=confidence,
            rationale=f'제조사 후보 {len(valid)}개 중 {best_source} 우선 선택',
        )

    def resolve_spec(self, ev: Evidence, policy: str) -> ResolvedField:
        """
        표준규격 결정
        - 노이즈 제거된 SPEC 기반
        - 정책에 따라 핵심 속성 우선
        """
        parsed = ev.parsed_spec
        fragments = ev.spec_fragments

        policy_spec_keys = {
            'SPEC_CENTERED':  ['material', 'size', 'grade_no'],
            'MODEL_CENTERED': ['size', 'note'],
            'CHEM_CENTERED':  ['cas_no', 'cat_no', 'volume'],
            'BRAND_CENTERED': ['color', 'size', 'note'],
            'GENERIC':        ['size', 'material', 'note'],
        }

        keys = policy_spec_keys.get(policy, policy_spec_keys['GENERIC'])

        parts = []
        for key in keys:
            val = parsed.get(key, '')
            if val:
                parts.append(val)

        if not parts and fragments:
            from evidence.spec_parser import SpecParser
            parser = SpecParser()
            raw_spec = fragments[0][0] if fragments else ''
            spec_clean = parser.clean_spec(raw_spec)
            if spec_clean:
                return ResolvedField(
                    value=spec_clean,
                    source='current',
                    confidence='medium',
                    rationale='원본 SPEC 노이즈 제거 후 사용',
                )

        if parts:
            spec_value = ', '.join(parts)
            return ResolvedField(
                value=spec_value,
                source='spec_extract',
                confidence='high',
                rationale=f'파싱된 속성 조합: {keys}',
            )

        return ResolvedField(
            value='',
            source='fallback',
            confidence='low',
            rationale='규격 정보 없음',
        )

    def resolve_name(self, ev: Evidence, policy: str) -> ResolvedField:
        """표준품명 결정"""
        from data.product_name_map import normalize_product_name

        candidates = ev.name_candidates
        if not candidates:
            return ResolvedField(value='', source='fallback', confidence='low',
                                 rationale='품명 후보 없음')

        priority = {'memo_override': 1, 'current': 2, 'first_info': 3}
        sorted_candidates = sorted(candidates, key=lambda x: priority.get(x[1], 99))

        raw_name, source = sorted_candidates[0]

        std_name = normalize_product_name(raw_name)
        changed = std_name != raw_name

        return ResolvedField(
            value=std_name,
            source=source,
            confidence='high' if changed else 'medium',
            rationale=f'표준품명 변환: {raw_name} → {std_name}' if changed else f'원본 품명 사용: {source}',
        )

    # -------------------------------------------------------------------------
    # 헬퍼
    # -------------------------------------------------------------------------

    def _source_to_confidence(self, source: str) -> str:
        high_sources   = {'memo_override', 'current', 'first_info', 'spec_extract'}
        medium_sources = {'url_extract', 'text_extract', 'page_fact', 'naver_fact'}
        if source in high_sources:
            return 'high'
        if source in medium_sources:
            return 'medium'
        return 'low'

    def _is_sijungpum_exception(self, ev: Evidence) -> bool:
        name = ev.get_top_name().lower()
        spec = ' '.join([f for f, _ in ev.spec_fragments]).lower()
        combined = f'{name} {spec}'
        return any(kw in combined for kw in SIJUNGPUM_EXCEPTION_KEYWORDS)