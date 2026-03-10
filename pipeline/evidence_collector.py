"""
[2] EvidenceCollector
- 전체 행에서 증거 수집
- URL / 변경지시 / 규격 / 제조사후보 / 모델명후보 통합
- Evidence 객체 반환
"""

from __future__ import annotations

import re

from models.evidence import Evidence
from evidence.url_extractor import URLExtractor
from evidence.memo_classifier import MemoClassifier
from evidence.change_intent_detector import ChangeIntentDetector
from evidence.spec_parser import SpecParser
from utils.text_utils import clean_value


class EvidenceCollector:

    KNOWN_MAKERS = [
        '밀워키', '디월트', '마끼다', '보쉬', '자야', '스탠리', '계양',
        '삼성', 'LG', 'HP', 'MEGGITT', 'SMC', 'KOSO', 'YAMAWA',
        'ebmpapst', 'MELKIN SPORTS', 'MELKIN', '제로투히어로',
        '코스틱폼텍', '폼텍', '한국폼텍', 'MISUMI', '미스미',
        'DEWALT', 'MILWAUKEE', 'MAKITA', 'BOSCH',
    ]

    MODEL_PATTERNS = [
        r'\b[A-Z]{1,4}\d{1,4}[A-Z0-9\-]*\b',
        r'\b[A-Z0-9]+(?:-[A-Z0-9]+){1,}\b',
        r'\b\d{3}-\d{3}-\d{3}(?:-[A-Z0-9]+)*\b',
        r'\b[A-Z]{1,3}\d{1,4}[A-Z]?(?:-[A-Z0-9]+)*\b',
    ]

    def __init__(self):
        self.url_extractor = URLExtractor()
        self.memo_classifier = MemoClassifier()
        self.change_detector = ChangeIntentDetector()
        self.spec_parser = SpecParser()

    def collect(self, row: dict) -> Evidence:
        ev = Evidence()

        # 1) URL
        ev.urls = self.url_extractor.extract_from_fields(row)

        # 2) 변경 지시
        ev.change_intents = self.change_detector.detect(row)

        # 3) 메모 타입
        memo_text = row.get('메모', '')
        ev.memo_type = self.memo_classifier.classify(memo_text)

        # 4) 규격 파싱
        spec_sources = [
            (row.get('SPEC', ''), 'SPEC'),
            (row.get('최초규격', ''), '최초규격'),
        ]
        ev.parsed_spec = self.spec_parser.parse_multi(spec_sources)

        # 5) 규격 조각
        if row.get('SPEC'):
            ev.spec_fragments.append((row['SPEC'], 'SPEC'))
        if row.get('최초규격') and row.get('최초규격') != row.get('SPEC'):
            ev.spec_fragments.append((row['최초규격'], '최초규격'))

        # 6) 품명 후보
        ev.name_candidates = self._collect_name_candidates(row)

        # 7) 제조사 후보
        ev.maker_candidates = self._collect_maker_candidates(row, ev)

        # 8) 모델 후보
        ev.model_candidates = self._collect_model_candidates(row, ev)

        # 9) 브랜드 후보
        ev.brand_candidates = self._collect_brand_candidates(row, ev)

        # 10) 패키지 정보
        ev.package_info = self._extract_package_info(row)

        # 11) source map
        ev.source_map = {
            'name': ev.name_candidates[0][1] if ev.name_candidates else '',
            'maker': ev.maker_candidates[0][1] if ev.maker_candidates else '',
            'model': ev.model_candidates[0][1] if ev.model_candidates else '',
            'brand': ev.brand_candidates[0][1] if ev.brand_candidates else '',
            'urls': len(ev.urls),
            'change_intents': len(ev.change_intents),
        }

        return ev

    # ------------------------------------------------------------------
    # 후보 수집
    # ------------------------------------------------------------------

    def _collect_name_candidates(self, row: dict) -> list:
        candidates = []

        # 변경지시(품명)
        for intent in row.get('_change_intents', []):
            if intent.get('field') == 'name':
                candidates.append((intent['value'], 'memo_override'))

        current = clean_value(row.get('품명', ''))
        if current:
            candidates.append((current, 'current'))

        first = clean_value(row.get('최초품명', ''))
        if first and first != current:
            candidates.append((first, 'first_info'))

        return self._dedupe_candidates(candidates)

    def _collect_maker_candidates(self, row: dict, ev: Evidence) -> list:
        candidates = []

        # SPEC 구조화 maker
        inline_maker = ev.parsed_spec.get('inline_maker', '')
        if inline_maker:
            candidates.append((inline_maker, 'spec_extract'))

        # 현재 제조사
        current = clean_value(row.get('제조사', ''))
        if current:
            candidates.append((current, 'current'))

        # 최초 제조사
        first = clean_value(row.get('최초제조사', ''))
        if first and first != current:
            candidates.append((first, 'first_info'))

        # SPEC 원문 자유문장 fallback
        spec_text = clean_value(row.get('SPEC', ''))
        free_maker = self._extract_freeform_maker(spec_text)
        if free_maker:
            candidates.append((free_maker, 'spec_extract'))

        # URL 힌트
        url_hints = self.url_extractor.extract_store_names(ev.urls)
        for name, _src in url_hints:
            candidates.append((name, 'url_extract'))

        # 메모/텍스트 추천업체명
        memo_maker = self._extract_memo_maker(row.get('메모', ''))
        if memo_maker:
            candidates.append((memo_maker, 'text_extract'))

        return self._dedupe_candidates(candidates)

    def _collect_model_candidates(self, row: dict, ev: Evidence) -> list:
        candidates = []

        # 변경지시(모델명)
        model_override = self.change_detector.get_model_override(ev.change_intents)
        if model_override:
            candidates.append((model_override, 'memo_override'))

        # SPEC 구조화 model
        inline_model = ev.parsed_spec.get('inline_model', '')
        if inline_model:
            candidates.append((inline_model, 'spec_extract'))

        # 현재 모델명
        current = clean_value(row.get('모델명', ''))
        if current:
            candidates.append((current, 'current'))

        # 최초 모델명
        first = clean_value(row.get('최초모델명', ''))
        if first and first != current:
            candidates.append((first, 'first_info'))

        # SPEC 원문 자유문장 fallback
        spec_text = clean_value(row.get('SPEC', ''))
        free_model = self._extract_freeform_model(spec_text)
        if free_model:
            candidates.append((free_model, 'spec_extract'))

        return self._dedupe_candidates(candidates)

    def _collect_brand_candidates(self, row: dict, ev: Evidence) -> list:
        candidates = []

        current = clean_value(row.get('브랜드', ''))
        if current:
            candidates.append((current, 'current'))

        maker_current = clean_value(row.get('제조사', ''))
        if maker_current:
            candidates.append((maker_current, 'current'))

        url_hints = self.url_extractor.extract_store_names(ev.urls)
        for name, _src in url_hints:
            candidates.append((name, 'url_extract'))

        return self._dedupe_candidates(candidates)

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def _extract_memo_maker(self, memo: str) -> str:
        if not memo:
            return ''
        m = re.search(r'추천업체명\s*[:：]\s*([^\n,/]+)', str(memo))
        if m:
            return m.group(1).strip()
        return ''

    def _extract_freeform_maker(self, text: str) -> str:
        text = str(text or '')
        for mk in self.KNOWN_MAKERS:
            if mk.lower() in text.lower():
                return mk
        return ''

    def _extract_freeform_model(self, text: str) -> str:
        text = str(text or '')
        for pat in self.MODEL_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                cand = m.group(0).strip()

                if re.fullmatch(r'\d+(?:mm|cm|m|kg|g|ml|l|bar|psi)', cand, re.IGNORECASE):
                    continue
                if re.fullmatch(r'[A-Z]{1,2}', cand):
                    continue
                if re.fullmatch(r'\d+', cand):
                    continue

                return cand
        return ''

    def _extract_package_info(self, row: dict) -> dict:
        info = {'unit': '', 'count': 1, 'note': ''}

        unit = clean_value(row.get('단위', ''))
        customer_unit = clean_value(row.get('고객단위', ''))
        info['unit'] = customer_unit or unit

        spec = row.get('SPEC', '')
        m = re.search(r'(\d+)\s*(?:EA|매|개)\s*/\s*(?:PK|BOX|팩|PAC)', str(spec), re.IGNORECASE)
        if m:
            info['count'] = int(m.group(1))
            info['note'] = m.group(0)

        return info

    def _dedupe_candidates(self, candidates: list) -> list:
        seen = set()
        result = []
        for value, source in candidates:
            v = clean_value(value)
            if not v:
                continue
            key = (v.lower(), source)
            if key in seen:
                continue
            seen.add(key)
            result.append((v, source))
        return result