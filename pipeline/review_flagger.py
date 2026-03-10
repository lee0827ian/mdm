"""
[8] ReviewFlagger
- 표준화 결과에 검토 플래그 부착
- 자동확정 가능 / 수동검토 필요 분류
"""

from models.evidence import Evidence
from models.resolved_field import ResolvedField


class ReviewFlagger:

    # 플래그 정의
    FLAG_MAKER_MISSING        = 'FLAG_MAKER_MISSING'
    FLAG_MODEL_MISSING        = 'FLAG_MODEL_MISSING'
    FLAG_STORE_AS_MAKER       = 'FLAG_STORE_AS_MAKER'
    FLAG_MEMO_OVERRIDE        = 'FLAG_MEMO_OVERRIDE'
    FLAG_CUSTOM_ORDER         = 'FLAG_CUSTOM_ORDER'
    FLAG_NONSTANDARD_REQUEST  = 'FLAG_NONSTANDARD_REQUEST'
    FLAG_CONFLICT_MAKER       = 'FLAG_CONFLICT_MAKER'
    FLAG_CONFLICT_MODEL       = 'FLAG_CONFLICT_MODEL'
    FLAG_FIRSTINFO_DIFF       = 'FLAG_FIRSTINFO_DIFF'
    FLAG_URL_ONLY_EVIDENCE    = 'FLAG_URL_ONLY_EVIDENCE'
    FLAG_SPEC_FRAGMENTED      = 'FLAG_SPEC_FRAGMENTED'
    FLAG_LOW_CONFIDENCE       = 'FLAG_LOW_CONFIDENCE'
    FLAG_CATEGORY_UNKNOWN     = 'FLAG_CATEGORY_UNKNOWN'
    FLAG_SIJUNGPUM            = 'FLAG_SIJUNGPUM'

    def flag(self, row: dict, ev: Evidence, fields: dict,
             policy: str) -> list:
        """
        전체 플래그 생성
        반환: [플래그 문자열 리스트]
        """
        flags = []

        제조사  = fields.get('제조사', ResolvedField())
        모델명  = fields.get('모델명', ResolvedField())
        표준품명 = fields.get('표준품명', ResolvedField())

        # ── 필드 누락 ──────────────────────────────────────────────────────
        if 제조사.is_empty() or 제조사.value in ('시중품', ''):
            if 제조사.value == '시중품':
                flags.append(self.FLAG_SIJUNGPUM)
            else:
                flags.append(self.FLAG_MAKER_MISSING)

        if 모델명.is_empty():
            flags.append(self.FLAG_MODEL_MISSING)

        # ── 스토어명이 제조사로 입력됨 ────────────────────────────────────
        if 제조사.rationale and 'store_generic' in 제조사.rationale:
            flags.append(self.FLAG_STORE_AS_MAKER)

        # ── 메모 기준 값 변경 ─────────────────────────────────────────────
        if any(i['type'] == 'model_change' for i in ev.change_intents):
            flags.append(self.FLAG_MEMO_OVERRIDE)

        # ── 변경 지시 타입 ────────────────────────────────────────────────
        if any(i['type'] == 'custom_order' for i in ev.change_intents):
            flags.append(self.FLAG_CUSTOM_ORDER)
        if any(i['type'] == 'nonstandard' for i in ev.change_intents):
            flags.append(self.FLAG_NONSTANDARD_REQUEST)

        # ── 현재값 vs 최초값 충돌 ─────────────────────────────────────────
        cur_maker  = row.get('제조사', '')
        first_maker = row.get('최초제조사', '')
        if cur_maker and first_maker and cur_maker != first_maker:
            flags.append(self.FLAG_CONFLICT_MAKER)

        cur_model  = row.get('모델명', '')
        first_model = row.get('최초모델명', '')
        if cur_model and first_model and cur_model != first_model:
            flags.append(self.FLAG_CONFLICT_MODEL)

        # ── 현재값과 최초값 자체가 다름 ───────────────────────────────────
        cur_name  = row.get('품명', '')
        first_name = row.get('최초품명', '')
        if cur_name and first_name and cur_name != first_name:
            flags.append(self.FLAG_FIRSTINFO_DIFF)

        # ── URL만 근거 ────────────────────────────────────────────────────
        has_internal = any(
            s in ('current', 'first_info', 'spec_extract', 'memo_override')
            for s in [제조사.source, 모델명.source]
        )
        if ev.has_url() and not has_internal:
            flags.append(self.FLAG_URL_ONLY_EVIDENCE)

        # ── 규격 분산 ────────────────────────────────────────────────────
        if len(ev.spec_fragments) > 1:
            flags.append(self.FLAG_SPEC_FRAGMENTED)

        # ── 낮은 신뢰도 ──────────────────────────────────────────────────
        low_conf_fields = [
            f for f in [표준품명, 제조사, 모델명]
            if f.confidence == 'low' and not f.is_empty()
        ]
        if len(low_conf_fields) >= 2:
            flags.append(self.FLAG_LOW_CONFIDENCE)

        # ── 대분류 미확인 ─────────────────────────────────────────────────
        if not row.get('대분류') and policy == 'GENERIC':
            flags.append(self.FLAG_CATEGORY_UNKNOWN)

        return list(dict.fromkeys(flags))  # 중복 제거

    def needs_manual_review(self, flags: list) -> bool:
        """수동 검토 필요 여부"""
        critical_flags = {
            self.FLAG_MAKER_MISSING,
            self.FLAG_MODEL_MISSING,
            self.FLAG_CONFLICT_MAKER,
            self.FLAG_CONFLICT_MODEL,
            self.FLAG_LOW_CONFIDENCE,
            self.FLAG_URL_ONLY_EVIDENCE,
            self.FLAG_STORE_AS_MAKER,
        }
        return any(f in critical_flags for f in flags)