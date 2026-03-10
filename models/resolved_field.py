from dataclasses import dataclass, field


@dataclass
class ResolvedField:
    """
    표준화된 단일 필드값 + 근거.
    StandardFieldResolver가 최종 결정한 각 항목에 사용.
    """

    # 최종 확정값
    value: str = ''

    # 값의 출처
    # 'current'       : 현재 작업 컬럼값
    # 'first_info'    : 최초상품정보 컬럼값
    # 'memo_override' : 메모/사유에서 명시적 수정 지시
    # 'spec_extract'  : SPEC 텍스트에서 추출
    # 'text_extract'  : 자유텍스트에서 추출
    # 'page_fact'     : URL 크롤링으로 확인
    # 'naver_fact'    : 네이버 검색으로 확인
    # 'rule'          : 규칙 기반 변환 (시중품, 처리불가 등)
    # 'fallback'      : 기본값 / 미확인
    source: str = 'fallback'

    # 신뢰도
    # 'high'   : 내부 증거 명확 or 내부+외부 일치
    # 'medium' : 외부 검색으로 추정
    # 'low'    : 단편 증거, 추정 불확실
    confidence: str = 'low'

    # 결정 근거 설명
    rationale: str = ''

    # 표준 DB 매핑 결과 ← 추가 (standard_matcher 전용)
    # 매핑 성공 시 std_item dict, 실패 시 빈 dict
    std_item: dict = field(default_factory=dict)

    # 표준 속성 정의 목록 ← 추가 (attr_validator 전용)
    # [{'속성순서': 1, '속성명': '재질'}, ...] 형태
    attrs: list = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.value or self.value.strip() == ''

    def is_confirmed(self) -> bool:
        return self.confidence == 'high'

    def is_std_matched(self) -> bool:
        """표준 DB 매핑 성공 여부"""
        return bool(self.std_item)

    def to_display(self) -> str:
        """결과 파일 출력용 (값만)"""
        return self.value

    def to_log(self) -> str:
        """로그 출력용 (값 + 근거)"""
        return (
            f"[{self.value}] source={self.source} conf={self.confidence} "
            f"std_matched={self.is_std_matched()} | {self.rationale}"
        )