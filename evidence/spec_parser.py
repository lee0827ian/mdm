"""
SpecParser - 규격 자유텍스트 구조화 (자유문장 maker/model 추출 강화)

강화 포인트:
- SPEC 내 Maker:/Model:/SIZE:/MATERIAL: 키:값 파싱
- 대괄호 형태 [SIZE:4IN][MATERIAL:A105] 파싱
- 자유문장형 '밀워키 M18 FPD2-0X ...' maker/model 추출
- 내부코드/시리얼번호 노이즈 제거
- 다중 소스 입력 지원 (SPEC + 최초규격 + 메모)
"""

from __future__ import annotations

import re
from typing import Tuple

from data.material_keywords import MATERIAL_LOOKUP
from utils.text_utils import (
    extract_bracket_content,
    remove_noise_patterns,
)
from config import SPEC_NOISE_PATTERNS


class SpecParser:

    COLOR_KEYWORDS = [
        'RED', 'BLUE', 'BLACK', 'WHITE', 'YELLOW', 'GREEN',
        'BROWN', 'PURPLE', 'ORANGE', 'GRAY', 'GREY', 'SILVER',
        'GOLD', 'PINK', '빨강', '파랑', '검정', '흰색', '흰', '백색',
        '노랑', '초록', '회색', '갈색', '청색', '딥블랙', '스카이블루',
    ]

    NOTE_STOP_WORDS = {
        'EA', 'PK', 'SET', 'BOX', 'ROL', 'PAC', 'DR', 'LOT',
        'MM', 'CM', 'M', 'IN', 'G', 'KG', 'ML', 'L', 'MG',
    }

    INLINE_KEY_PATTERNS = {
        'maker': [
            r'(?:Maker|MAKER|제조사|MFGR?)\s*[:：]\s*([^,\]\n]+)',
            r'MAKER\s+P/N\s*[:：]\s*([^,\]\n]+)',
        ],
        'model': [
            r'(?:Model|MODEL|모델)\s*[:：]\s*([^,\]\n,/]+)',
            r'M/PN\s*[:：]\s*([^,\]\n]+)',
            r'P/N\s*[:：]\s*([^,\]\n]+)',
        ],
        'size': [
            r'(?:SIZE|Size|규격)\s*[:：]\s*([^,\]\n]+)',
        ],
        'material': [
            r'(?:MATERIAL|Material|재질)\s*[:：]\s*([^,\]\n]+)',
        ],
        'serial': [
            r'S/N\s*[:：]\s*([^,\]\n]+)',
            r'D/N\s*[:：]\s*([^,\]\n]+)',
        ],
    }

    # 자유문장형 제조사 후보
    KNOWN_MAKERS = [
        '밀워키', '디월트', '마끼다', '보쉬', '자야', '스탠리', '계양',
        '삼성', 'LG', 'HP', 'MEGGITT', 'SMC', 'KOSO', 'YAMAWA',
        'ebmpapst', 'MELKIN SPORTS', 'MELKIN', '제로투히어로',
        '코스틱폼텍', '폼텍', '한국폼텍', 'MISUMI', '미스미',
        'DEWALT', 'MILWAUKEE', 'MAKITA', 'BOSCH',
    ]

    # 자유문장형 모델 패턴
    MODEL_LIKE_PATTERNS = [
        r'\b[A-Z]{1,4}\d{1,4}[A-Z0-9\-]*\b',                  # M18, IPC707, PRF308
        r'\b[A-Z0-9]+(?:-[A-Z0-9]+){1,}\b',                  # FPD2-0X, EO-IC100BBEGKR
        r'\b\d{3}-\d{3}-\d{3}(?:-[A-Z0-9]+)*\b',             # 111-902-000-011-A5
        r'\b[A-Z]{1,3}\d{1,4}[A-Z]?(?:-[A-Z0-9]+)*\b',       # MHL2-20D, TNPT01L
    ]

    def parse(self, spec_text: str) -> dict:
        result = {
            'size': '', 'material': '', 'grade_no': '',
            'cas_no': '', 'cat_no': '', 'color': '',
            'volume': '', 'note': '',
            'inline_maker': '', 'inline_model': '',
        }

        if not spec_text or str(spec_text).strip() == '':
            return result

        spec = str(spec_text).strip()
        spec_clean = remove_noise_patterns(spec, SPEC_NOISE_PATTERNS)

        # 1) [KEY:VALUE] 파싱
        bracket_data = self._parse_brackets(spec_clean)
        for key, val in bracket_data.items():
            k = key.upper()
            if k in ('SIZE',) and not result['size']:
                result['size'] = val
            elif k in ('MATERIAL',) and not result['material']:
                result['material'] = val
            elif k in ('PRESS. RATING', 'SCHEDULE/THICKNESS', 'END CONN. TYPE',
                       'TYPE', 'OTHER SPEC') and not result['note']:
                result['note'] = val

        # 2) Maker:/Model: 명시형 파싱
        inline = self._parse_inline(spec_clean)
        if inline.get('maker'):
            result['inline_maker'] = inline['maker'].strip()
        if inline.get('model'):
            result['inline_model'] = inline['model'].strip()
        if inline.get('size') and not result['size']:
            result['size'] = inline['size'].strip()
        if inline.get('material') and not result['material']:
            result['material'] = inline['material'].strip()

        # 3) 자유문장형 maker/model 파싱
        free_maker, free_model = self._extract_freeform_maker_model(spec_clean)
        if free_maker and not result['inline_maker']:
            result['inline_maker'] = free_maker
        if free_model and not result['inline_model']:
            result['inline_model'] = free_model

        spec_upper = spec_clean.upper()

        # 4) CAS
        if not result['cas_no']:
            m = re.search(r'\b(\d{2,7}-\d{2}-\d)\b', spec_clean)
            if m:
                result['cas_no'] = m.group(1)

        # 5) CAT NO
        if not result['cat_no']:
            m = re.search(
                r'(?:CAT\.?\s*NO\.?\s*)?(SC-\d{5,}|[A-Z]{2,4}-\d{5,}|\d{6,}-\d{3})',
                spec_upper
            )
            if m:
                result['cat_no'] = m.group(1)

        # 6) size
        if not result['size']:
            result['size'] = self._extract_size(spec_clean)

        # 7) material
        if not result['material']:
            result['material'] = self._extract_material(spec_upper)

        # 8) grade_no
        if not result['grade_no']:
            result['grade_no'] = self._extract_grade(spec_clean)

        # 9) volume
        if not result['volume']:
            m = re.search(r'\b(\d+\.?\d*)\s*(mg|mL|g|kg|L)\b', spec_clean, re.IGNORECASE)
            if m:
                result['volume'] = m.group().strip()

        # 10) color
        if not result['color']:
            for color in self.COLOR_KEYWORDS:
                if color.upper() in spec_upper:
                    result['color'] = color
                    break

        # 11) note
        if not result['note']:
            result['note'] = self._extract_note(spec_clean, result)

        return result

    def parse_multi(self, sources: list) -> dict:
        merged = {
            'size': '', 'material': '', 'grade_no': '',
            'cas_no': '', 'cat_no': '', 'color': '',
            'volume': '', 'note': '',
            'inline_maker': '', 'inline_model': '',
        }
        for text, _source in sources:
            parsed = self.parse(text)
            for key, val in parsed.items():
                if val and not merged[key]:
                    merged[key] = val
        return merged

    def clean_spec(self, spec_text: str) -> str:
        if not spec_text:
            return ''
        return remove_noise_patterns(str(spec_text), SPEC_NOISE_PATTERNS).strip()

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _parse_brackets(self, text: str) -> dict:
        result = {}
        for item in extract_bracket_content(text):
            m = re.match(r'([^:]+?)\s*:\s*(.+)', item.strip())
            if m:
                result[m.group(1).strip()] = m.group(2).strip()
        return result

    def _parse_inline(self, text: str) -> dict:
        result = {}
        for field, patterns in self.INLINE_KEY_PATTERNS.items():
            if field == 'serial':
                continue
            for pattern in patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    result[field] = m.group(1).strip().rstrip(',').strip()
                    break
        return result

    def _extract_freeform_maker_model(self, text: str) -> Tuple[str, str]:
        """
        예:
        - 밀워키 M18 FPD2-0X 충전햄머드릴 ...
        - 삼성 EO-IC100BBEGKR 이어폰
        - HP 527pf Monitor
        """
        maker = ''
        model = ''

        text_clean = str(text).strip()
        text_upper = text_clean.upper()

        # 1) maker 먼저 탐색
        for mk in self.KNOWN_MAKERS:
            if mk.lower() in text_clean.lower():
                maker = mk
                break

        # 2) maker 근처 모델 탐색
        if maker:
            idx = text_clean.lower().find(maker.lower())
            tail = text_clean[idx + len(maker):].strip()
            model = self._extract_model_like(tail)

        # 3) maker 못 찾았어도 모델 패턴은 시도
        if not model:
            model = self._extract_model_like(text_clean)

        return maker, model

    def _extract_model_like(self, text: str) -> str:
        for pat in self.MODEL_LIKE_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                cand = m.group(0).strip()

                # 단위/압력/수량 제외
                if re.fullmatch(r'\d+(?:mm|cm|m|kg|g|ml|l|bar|psi)', cand, re.IGNORECASE):
                    continue
                if re.fullmatch(r'[A-Z]{1,2}', cand):
                    continue
                if re.fullmatch(r'\d+', cand):
                    continue

                return cand
        return ''

    def _extract_size(self, spec: str) -> str:
        size_patterns = [
            r'(?:ID|OD)\s*\d+\.?\d*\s*(?:mm)?',
            r'DIA\s*\d+\.?\d*\s*(?:mm)?',
            r'\d+\.?\d*\s*(?:mm|m|cm)\s*[*xX×]\s*\d+\.?\d*\s*(?:mm|m|cm)',
            r'\d+\.?\d*\s*IN(?:CH)?',
            r'AS-?568[A-Z]?-?\d+',
            r'\d+\s*호',
            r'\d+\.?\d*\s*mm',
            r'\d+\s*[*xX×]\s*\d+\s*[*xX×]\s*\d+',
            r'\d+\s*[*xX×]\s*\d+',
            r'\d+-\d+/\d+\s*IN',
            r'\d+/\d+\s*(?:IN|INCH)',
            r'#\s*\d+',
            r'\d+\s*(?:bar|BAR|PSI)',
        ]
        for pattern in size_patterns:
            m = re.search(pattern, spec, re.IGNORECASE)
            if m:
                return m.group().strip()
        return ''

    def _extract_material(self, spec_upper: str) -> str:
        best_mat = ''
        best_len = 0
        for kw_upper, (_cat, kw) in MATERIAL_LOOKUP.items():
            pattern = r'(?<![A-Z0-9])' + re.escape(kw_upper) + r'(?![A-Z0-9])'
            m = re.search(pattern, spec_upper)
            if m and len(kw_upper) > best_len:
                best_len = len(kw_upper)
                best_mat = kw
        return best_mat

    def _extract_grade(self, spec: str) -> str:
        m = re.search(r'#\s*\d+', spec)
        if m:
            return m.group().strip()
        m = re.search(r'AS-?568[A-Z]?-?\d+', spec, re.IGNORECASE)
        if m:
            return m.group().strip()
        return ''

    def _extract_note(self, spec: str, parsed: dict) -> str:
        text = spec
        for v in parsed.values():
            if v:
                text = text.replace(str(v), ' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:120]