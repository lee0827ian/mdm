from dataclasses import dataclass, field


@dataclass
class Evidence:
    """
    EvidenceCollector가 수집한 모든 증거를 담는 객체.
    각 후보값은 (값, 출처) 튜플 리스트로 관리.
    """

    # 품명 후보: [(값, 출처), ...]
    name_candidates: list = field(default_factory=list)

    # 제조사 후보: [(값, 출처), ...]
    maker_candidates: list = field(default_factory=list)

    # 모델명 후보: [(값, 출처), ...]
    model_candidates: list = field(default_factory=list)

    # 브랜드 후보: [(값, 출처), ...]
    brand_candidates: list = field(default_factory=list)

    # 규격 조각들: [(값, 출처), ...]
    spec_fragments: list = field(default_factory=list)

    # 추출된 URL 목록
    urls: list = field(default_factory=list)

    # 변경 지시 감지 결과: [{'type': str, 'value': str, 'raw': str}, ...]
    change_intents: list = field(default_factory=list)

    # 메모 타입 분류
    # 'explicit_change' | 'url_reference' | 'option_hint' | 'history_log' | 'mixed' | 'empty'
    memo_type: str = 'empty'

    # 각 후보값의 출처 추적
    # {'maker': '현재값', 'model': '메모수정', ...}
    source_map: dict = field(default_factory=dict)

    # 파싱된 규격 구조체 (SpecParser 결과)
    parsed_spec: dict = field(default_factory=dict)

    # 입수량/패키지 정보
    package_info: dict = field(default_factory=dict)

    def has_url(self) -> bool:
        return len(self.urls) > 0

    def has_change_intent(self) -> bool:
        return len(self.change_intents) > 0

    def get_top_maker(self) -> str:
        """가장 우선순위 높은 제조사 후보 반환"""
        if self.maker_candidates:
            return self.maker_candidates[0][0]
        return ''

    def get_top_model(self) -> str:
        """가장 우선순위 높은 모델명 후보 반환"""
        if self.model_candidates:
            return self.model_candidates[0][0]
        return ''

    def get_top_name(self) -> str:
        """가장 우선순위 높은 품명 후보 반환"""
        if self.name_candidates:
            return self.name_candidates[0][0]
        return ''