"""
[10] AttrValidator
- 표준품명 매핑 후 필수 속성 충족 여부 검증
- SPEC 파싱 결과와 표준 속성 정의 대조
- 미충족 속성 목록 반환 → FLAG_ATTR_INCOMPLETE

spec_parser 실제 반환 키:
  size, material, grade_no, cas_no, cat_no, color, volume, note,
  inline_maker, inline_model
"""

import re
from models.resolved_field import ResolvedField
from models.evidence import Evidence


class AttrValidator:
    """
    표준 속성 충족 검증.
    StandardMatcherStep.match() 결과(attrs)를 기반으로 동작.
    """

    # 항상 선택 속성으로 처리
    OPTIONAL_ATTRS = {'비고', '기타', '참고', '특이사항'}

    # 표준 속성명 → spec_parser 키 매핑
    ATTR_KEY_MAP: dict[str, list[str]] = {
        # 크기/치수류
        '사이즈':   ['size'],
        '규격':     ['size', 'grade_no'],
        '크기':     ['size'],
        '치수':     ['size'],
        '길이':     ['size'],
        '직경':     ['size'],
        '외경':     ['size'],
        '내경':     ['size'],
        '두께':     ['size'],
        # 재질류
        '재질':     ['material'],
        '소재':     ['material'],
        '재료':     ['material'],
        # 용량/중량류
        '용량':     ['volume', 'size'],
        '중량':     ['volume'],
        '무게':     ['volume'],
        '입수량':   ['volume', 'note'],
        # 색상
        '색상':     ['color'],
        '컬러':     ['color'],
        # 등급/규격번호
        '등급':     ['grade_no', 'note'],
        '규격번호': ['grade_no'],
        '품번':     ['grade_no', 'cat_no'],
        # 화학/실험류
        'CAS번호':  ['cas_no'],
        'CAT번호':  ['cat_no'],
        # 전기/계측류
        '정격전압': ['note', 'size'],
        '출력(W)':  ['note', 'volume'],
        '전압':     ['note', 'size'],
        '전류':     ['note'],
        '압력':     ['note', 'size'],
        '온도':     ['note', 'size'],
        '측정범위': ['note', 'size'],
        '검출거리': ['size', 'note'],
        '검출타입': ['note', 'material'],
        '감도':     ['note', 'grade_no'],
        '입력사양': ['note'],
        '배선사양': ['note'],
        '타입':     ['note', 'material'],
        # 기타
        '향기종류': ['note', 'color'],
        '수량':     ['volume', 'note'],
        '단위':     ['note'],
    }

    # spec_text 원문 키워드 탐색 테이블
    KEYWORD_HINTS: dict[str, list[str]] = {
        '검출타입': ['비접촉식', '접촉식', '유도형', '용량형', '광학식'],
        '타입':     ['일체형', '분리형', '내장형', '외장형'],
        '재질':     ['STS', 'SS', 'PU', 'PE', 'PP', 'SUS', '스테인리스', '알루미늄', '철', '동'],
        '색상':     ['백색', '흑색', '적색', '청색', '녹색', 'BLACK', 'WHITE', 'RED', 'BLUE'],
        '배선사양': ['동축', '케이블', '2선', '3선', '4선', 'NPN', 'PNP'],
        # ── 등급 키워드 추가 ──────────────────────────────────────────────
        '등급':     [
            'CLASS I', 'CLASS II', 'CLASS III',
            'CLASS 1', 'CLASS 2', 'CLASS 3',
            'IP65', 'IP67', 'IP68', 'IP54', 'IP44',
            'GRADE A', 'GRADE B', 'GRADE C',
            'A급', 'B급', 'C급',
            '1급', '2급', '3급',
        ],
    }

    # 수치+단위 패턴 탐색 테이블
    NUM_UNIT_PATTERNS: dict[str, str] = {
        '중량':     r'(\d+(?:\.\d+)?\s*(?:kg|g|KG|G))',
        '무게':     r'(\d+(?:\.\d+)?\s*(?:kg|g|KG|G))',
        '용량':     r'(\d+(?:\.\d+)?\s*(?:ml|ML|L|l|cc|CC))',
        '정격전압': r'(\d+(?:\.\d+)?\s*(?:V|v|VAC|VDC))',
        '전압':     r'(\d+(?:\.\d+)?\s*(?:V|v|VAC|VDC))',
        '출력(W)':  r'(\d+(?:\.\d+)?\s*(?:W|w|KW|kW))',
        '전류':     r'(\d+(?:\.\d+)?\s*(?:A|mA|MA))',
        '압력':     r'(\d+(?:\.\d+)?\s*(?:bar|Bar|BAR|MPa|kPa|psi|PSI))',
        '온도':     r'(\d+(?:\.\d+)?\s*(?:℃|°C|°F|K))',
        '측정범위': r'(\d+(?:\.\d+)?\s*(?:mm|cm|m|M|Hz|kHz|MHz))',
        '검출거리': r'(\d+(?:\.\d+)?\s*(?:mm|cm|m))',
        '감도':     r'([+\-±]\s*\d+(?:\.\d+)?\s*(?:mm|%|dB))',
        '입수량':   r'(\d+\s*(?:EA|개|매|PK|BOX|팩)\s*/\s*(?:PK|BOX|팩|EA))',
    }

    def validate(self, name_field: ResolvedField, ev: Evidence) -> dict:
        """
        속성 충족 검증 실행.

        반환:
        {
            'required_attrs': [...],
            'matched_attrs':  {...},
            'missing_attrs':  [...],
            'score': float,
            'flag': bool,
        }
        """
        attrs = getattr(name_field, 'attrs', [])

        if not attrs:
            return self._empty_result()

        required = [
            a['속성명'] for a in attrs
            if a['속성명'] and a['속성명'] not in self.OPTIONAL_ATTRS
        ]

        if not required:
            return self._empty_result()

        parsed_spec = ev.parsed_spec or {}
        spec_text   = ' '.join(f for f, _ in (ev.spec_fragments or []))

        matched = {}
        missing = []

        for attr in required:
            val = self._find_attr_value(attr, parsed_spec, spec_text, ev)
            if val:
                matched[attr] = val
            else:
                missing.append(attr)

        score = len(matched) / len(required) if required else 1.0

        return {
            'required_attrs': required,
            'matched_attrs':  matched,
            'missing_attrs':  missing,
            'score':          round(score, 2),
            'flag':           len(missing) > 0,
        }

    def _find_attr_value(self, attr_name: str, parsed_spec: dict,
                         spec_text: str, ev: Evidence) -> str:
        """
        속성값 탐색 순서:
        1. ATTR_KEY_MAP → parsed_spec 키 조회
        2. NUM_UNIT_PATTERNS → spec_text 수치+단위 패턴
        3. KEYWORD_HINTS → spec_text 키워드 탐색
        4. Evidence 패키지 정보
        """
        # ── 1. parsed_spec 키 매핑 ────────────────────────────────────────
        keys = self.ATTR_KEY_MAP.get(attr_name, [attr_name.lower()])
        for key in keys:
            val = parsed_spec.get(key, '')
            if val and str(val).strip():
                return str(val).strip()

        if spec_text:
            # ── 2. 수치+단위 패턴 탐색 ───────────────────────────────────
            pattern = self.NUM_UNIT_PATTERNS.get(attr_name)
            if pattern:
                m = re.search(pattern, spec_text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()

            # ── 3. 키워드 힌트 탐색 ───────────────────────────────────────
            hints = self.KEYWORD_HINTS.get(attr_name, [])
            for hint in hints:
                if hint.lower() in spec_text.lower():
                    return hint

        # ── 4. Evidence 패키지 정보 ───────────────────────────────────────
        pkg = getattr(ev, 'package_info', {}) or {}
        if attr_name in ('입수량', '수량') and pkg.get('count', 1) > 1:
            return str(pkg['count'])
        if attr_name == '단위' and pkg.get('unit'):
            return pkg['unit']

        return ''

    def format_missing_attrs(self, validation: dict) -> str:
        """미충족 속성 목록을 문자열로 포맷"""
        missing = validation.get('missing_attrs', [])
        score   = validation.get('score', 1.0)
        if not missing:
            return ''
        return f"속성미충족({int(score*100)}%): {', '.join(missing)}"

    @staticmethod
    def _empty_result() -> dict:
        return {
            'required_attrs': [],
            'matched_attrs':  {},
            'missing_attrs':  [],
            'score':          1.0,
            'flag':           False,
        }