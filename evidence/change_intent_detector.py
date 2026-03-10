"""
변경 지시 / 처리 방향 감지기
- 제작품/비표준/시중품 요청 감지
- 표준화 결과를 바꾸는 신호 탐지
"""

import re
from config import CHANGE_INTENT_PATTERNS


class ChangeIntentDetector:

    def detect(self, row: dict) -> list:
        """
        전체 행에서 변경 지시 감지
        반환: [{'type': str, 'value': str, 'raw': str, 'source': str}, ...]
        """
        results = []

        # 검사 대상 필드
        check_fields = {
            '메모':         row.get('메모', ''),
            '고객주문사유': row.get('고객주문사유', ''),
            '고객전체사유': row.get('고객전체사유', ''),
            'SPEC':         row.get('SPEC', ''),
            '최초규격':     row.get('최초규격', ''),
        }

        for field_name, text in check_fields.items():
            if not text:
                continue
            detected = self._detect_in_text(str(text), field_name)
            results.extend(detected)

        # 표준구분 컬럼 직접 확인
        std_type = str(row.get('표준구분', '')).strip()
        if '비표준' in std_type:
            results.append({
                'type': 'nonstandard',
                'value': std_type,
                'raw': std_type,
                'source': '표준구분',
            })

        return results

    def _detect_in_text(self, text: str, source: str) -> list:
        """단일 텍스트에서 변경 지시 감지"""
        results = []
        text_lower = text.lower()

        for intent_type, patterns in CHANGE_INTENT_PATTERNS.items():
            for pattern in patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    value = m.group(1) if m.lastindex else m.group(0)
                    results.append({
                        'type': intent_type,
                        'value': value.strip(),
                        'raw': m.group(0),
                        'source': source,
                    })
                    break  # 같은 타입은 첫 번째만

        return results

    def is_custom_order(self, intents: list) -> bool:
        """제작품/주문제작 여부"""
        return any(i['type'] == 'custom_order' for i in intents)

    def is_nonstandard(self, intents: list) -> bool:
        """비표준 확정 여부"""
        return any(i['type'] == 'nonstandard' for i in intents)

    def is_sijungpum_request(self, intents: list) -> bool:
        """시중품 요청 여부"""
        return any(i['type'] == 'sijungpum_request' for i in intents)

    def get_model_override(self, intents: list) -> str:
        """메모에서 명시적 모델명 변경 지시 추출"""
        for intent in intents:
            if intent['type'] == 'model_change':
                return intent['value']
        return ''

    def has_skip_signal(self, intents: list) -> tuple:
        """
        처리불가 신호 여부
        반환: (처리불가: bool, 사유: str)
        """
        if self.is_custom_order(intents):
            return True, '제작품/주문제작'
        if self.is_nonstandard(intents):
            return True, '비표준확정 요청'
        return False, ''