"""
[7] StandardFieldResolver
- 모든 증거를 종합해 최종 5개 표준 필드 결정
- 각 필드: value + source + confidence + rationale
"""

from models.evidence import Evidence
from models.resolved_field import ResolvedField
from pipeline.priority_resolver import SourcePriorityResolver
from pipeline.party_resolver import PartyResolver


class StandardFieldResolver:

    def __init__(self):
        self.priority_resolver = SourcePriorityResolver()
        self.party_resolver = PartyResolver()

    def resolve(self, row: dict, ev: Evidence,
                policy: str, fact_result: dict = None) -> dict:
        """
        최종 5개 표준 필드 결정
        반환: {표준품명, 표준규격, 제조사, 모델명, 브랜드} (각각 ResolvedField)
        """
        # FactFinder 결과 Evidence에 반영
        if fact_result and fact_result.get('success'):
            self._enrich_evidence_with_facts(ev, fact_result)

        # 각 필드 결정
        표준품명 = self.priority_resolver.resolve_name(ev, policy)
        표준규격 = self.priority_resolver.resolve_spec(ev, policy)
        모델명   = self.priority_resolver.resolve_model(ev)
        제조사_field = self.priority_resolver.resolve_maker(ev, policy)

        # PartyResolver로 제조사/브랜드 분리
        party = self.party_resolver.resolve(
            maker_value=제조사_field.value,
            brand_value=ev.brand_candidates[0][0] if ev.brand_candidates else '',
            urls=ev.urls,
        )

        제조사 = ResolvedField(
            value=party['maker'],
            source=제조사_field.source,
            confidence=party['confidence'],
            rationale=f"{제조사_field.rationale} | party_type={party['party_type']}",
        )

        브랜드 = ResolvedField(
            value=party['brand'],
            source=제조사_field.source,
            confidence=party['confidence'],
            rationale=f"party_type={party['party_type']}",
        )

        return {
            '표준품명': 표준품명,
            '표준규격': 표준규격,
            '제조사':   제조사,
            '모델명':   모델명,
            '브랜드':   브랜드,
        }

    def _enrich_evidence_with_facts(self, ev: Evidence, fact_result: dict):
        """FactFinder 결과를 Evidence에 추가"""
        confidence = fact_result.get('confidence', 'inferred')
        source = fact_result.get('source', 'naver_fact')

        # 'confirmed' → high, 'inferred' → medium
        conf_map = {'confirmed': 'high', 'inferred': 'medium', 'unresolved': 'low'}
        source_map = {'naver': 'naver_fact', 'page': 'page_fact'}
        mapped_source = source_map.get(source, source)

        for maker in fact_result.get('maker_candidates', []):
            if maker and maker not in [v for v, _ in ev.maker_candidates]:
                ev.maker_candidates.append((maker, mapped_source))

        for model in fact_result.get('model_candidates', []):
            if model and model not in [v for v, _ in ev.model_candidates]:
                ev.model_candidates.append((model, mapped_source))

        for brand in fact_result.get('brand_candidates', []):
            if brand and brand not in [v for v, _ in ev.brand_candidates]:
                ev.brand_candidates.append((brand, mapped_source))