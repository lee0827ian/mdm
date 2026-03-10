from dataclasses import dataclass, field
from models.resolved_field import ResolvedField


@dataclass
class StandardResult:
    """
    한 행의 최종 표준화 결과.
    엑셀 출력 및 로그에 사용.
    """

    # 식별자
    관리번호: str = ''

    # 원본값 (변경 전 보존)
    원본품명: str = ''
    원본SPEC: str = ''
    원본제조사: str = ''
    원본모델명: str = ''

    # 표준화 결과 (ResolvedField)
    표준품명: ResolvedField = field(default_factory=ResolvedField)
    표준규격: ResolvedField = field(default_factory=ResolvedField)
    제조사: ResolvedField = field(default_factory=ResolvedField)
    모델명: ResolvedField = field(default_factory=ResolvedField)
    브랜드: ResolvedField = field(default_factory=ResolvedField)

    # 처리 메타
    처리정책: str = ''
    플래그: list = field(default_factory=list)
    플래그_후보: list = field(default_factory=list)   # ← 추가: [9][10][11] 단계 플래그 누적용
    처리가능여부: bool = True
    처리불가사유: str = ''

    # 검증 결과 ← 추가
    속성검증: str = ''        # AttrValidator 결과 (미충족 속성 문자열)
    제조사검증: dict = field(default_factory=dict)  # MakerValidator 결과 전체

    def to_excel_row(self) -> dict:
        """엑셀 출력용 딕셔너리 변환"""
        maker_v = self.제조사검증
        return {
            '관리번호':       self.관리번호,
            '원본품명':       self.원본품명,
            '원본SPEC':      self.원본SPEC,
            '원본제조사':     self.원본제조사,
            '원본모델명':     self.원본모델명,
            '표준품명':       self.표준품명.to_display(),
            '표준규격':       self.표준규격.to_display(),
            '제조사':         self.제조사.to_display(),
            '모델명':         self.모델명.to_display(),
            '브랜드':         self.브랜드.to_display(),
            '처리정책':       self.처리정책,
            '신뢰도':         self._overall_confidence(),
            '플래그':         ' | '.join(self.플래그) if self.플래그 else '-',
            '품명근거':       self.표준품명.source,
            '규격근거':       self.표준규격.source,
            '제조사근거':     self.제조사.source,
            '모델명근거':     self.모델명.source,
            '처리가능여부':   'Y' if self.처리가능여부 else 'N',
            '처리불가사유':   self.처리불가사유,
            # ── 검증 결과 컬럼 추가 ──────────────────────────────────
            '속성충족여부':   '-' if not self.속성검증 else self.속성검증,
            '제조사표준여부': 'Y' if maker_v.get('is_standard') else (
                             '-' if maker_v.get('method') == 'skip' else 'N'
            ),
            '제조사매핑명':   maker_v.get('matched_name', ''),
            '제조사후보':     ' / '.join(
                c['maker_name'] for c in maker_v.get('candidates', [])
            ),
        }

    def _overall_confidence(self) -> str:
        """5개 필드 신뢰도 중 가장 낮은 것 기준"""
        levels = {'high': 3, 'medium': 2, 'low': 1}
        fields = [self.표준품명, self.제조사, self.모델명]
        min_level = min(levels.get(f.confidence, 1) for f in fields)
        return {3: 'H', 2: 'M', 1: 'L'}[min_level]