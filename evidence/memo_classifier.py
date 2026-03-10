"""
메모 타입 분류기
- explicit_change : 명시적 수정 지시 ("모델명 XXX로 변경")
- url_reference   : URL 포함 메모
- option_hint     : 옵션/구성품 힌트 ("50매, 스카이블루")
- history_log     : 구매 이력/납품 메모 (파싱 불필요)
- mixed           : 복합 타입
- empty           : 비어있음
"""

import re
from config import MEMO_TYPE_KEYWORDS


class MemoClassifier:

    def classify(self, memo_text: str) -> str:
        """
        메모 텍스트의 주요 타입 반환
        """
        if not memo_text or not memo_text.strip():
            return 'empty'

        text = str(memo_text)
        detected = []

        for memo_type, keywords in MEMO_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    detected.append(memo_type)
                    break

        if not detected:
            return 'empty'
        if len(detected) == 1:
            return detected[0]

        # 우선순위: explicit_change > url_reference > option_hint > history_log
        priority = ['explicit_change', 'url_reference', 'option_hint', 'history_log']
        for p in priority:
            if p in detected:
                return p if len(detected) == 1 else 'mixed'

        return 'mixed'

    def extract_option_hints(self, text: str) -> list:
        """
        옵션/구성품 힌트 추출
        예: "50매, 스카이블루" → ['50매', '스카이블루']
        예: "2EA/PK로 진행" → ['2EA/PK']
        """
        hints = []
        if not text:
            return hints

        # 수량 패턴
        qty_patterns = [
            r'\d+\s*매',
            r'\d+\s*EA\s*/\s*(?:PK|BOX|SET)',
            r'\d+\s*개입',
            r'\d+\s*개(?=\s|,|$)',
        ]
        for pattern in qty_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            hints.extend(matches)

        # 색상 힌트
        color_pattern = r'(?:색상|color)\s*[:：]?\s*([가-힣a-zA-Z]+)'
        matches = re.findall(color_pattern, text, re.IGNORECASE)
        hints.extend(matches)

        # 단순 색상명
        colors = ['스카이블루', '딥블랙', '블랙', '화이트', '실버', '골드',
                  'black', 'white', 'blue', 'red', 'silver']
        for color in colors:
            if color.lower() in text.lower():
                hints.append(color)

        return list(dict.fromkeys(hints))  # 중복 제거

    def is_history_log(self, text: str) -> bool:
        """구매 이력/납품 로그 여부 (파싱 스킵 대상)"""
        if not text:
            return False
        history_markers = [
            'PR NO', '구매요청명', '납품장소', '납기', '담당자',
            '납품요구일', '구매 사유', '구매 품목',
        ]
        count = sum(1 for m in history_markers if m in text)
        return count >= 2

    def extract_change_instructions(self, text: str) -> list:
        """
        명시적 변경 지시 추출
        예: "모델명 P5000G로 변경 부탁합니다" → [{'field': 'model', 'value': 'P5000G'}]
        """
        instructions = []
        if not text:
            return instructions

        # 모델명 변경
        model_patterns = [
            r'모델명?\s+([A-Za-z0-9\-_]+)\s*(?:으?로|로)\s*변경',
            r'모델\s*변경\s*[:\s]+([A-Za-z0-9\-_]+)',
            r'품명\s*:\s*([가-힣a-zA-Z0-9\-_ ]+)\s*(?:으?로|로)\s*진행',
        ]
        for pattern in model_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                instructions.append({
                    'field': 'model',
                    'value': m.group(1).strip(),
                    'raw': m.group(0),
                })

        # 품명 변경
        name_patterns = [
            r'품명\s*:\s*([가-힣a-zA-Z0-9\-_ ]+)\s*(?:으?로|로)\s*진행',
            r'([가-힣a-zA-Z0-9\-_ ]+)(?:으?로|로)\s*진행\s*가능',
        ]
        for pattern in name_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                instructions.append({
                    'field': 'name',
                    'value': m.group(1).strip(),
                    'raw': m.group(0),
                })

        return instructions