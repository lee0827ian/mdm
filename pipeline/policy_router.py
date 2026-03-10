"""
[3] StandardizationPolicyRouter
- 품목 유형 판별 → 표준화 정책 결정
- 처리불가 여부 판단
"""

from models.evidence import Evidence
from data.policy_rules import POLICY_RULES, POLICY_PRIORITY
from utils.text_utils import clean_value


class StandardizationPolicyRouter:

    def route(self, row: dict, ev: Evidence) -> tuple:
        """
        정책 결정
        반환: (policy: str, skip: bool, skip_reason: str)
        """
        # 처리불가 신호 먼저 확인
        skip, reason = self._check_skip(row, ev)
        if skip:
            return 'SKIP', True, reason

        # 품목 유형별 정책 결정
        policy = self._determine_policy(row, ev)
        return policy, False, ''

    def _check_skip(self, row: dict, ev: Evidence) -> tuple:
        """처리불가 여부 확인"""
        from evidence.change_intent_detector import ChangeIntentDetector
        detector = ChangeIntentDetector()

        # 변경 지시에서 처리불가 신호
        skip, reason = detector.has_skip_signal(ev.change_intents)
        if skip:
            return True, reason

        # 품명/SPEC이 완전히 비어있거나 의미없는 경우
        name = clean_value(row.get('품명', ''))
        spec = clean_value(row.get('SPEC', ''))
        if not name and not spec:
            return True, '품명/규격 모두 없음'

        # 정책 키워드로 SKIP 확인
        for policy in ['SKIP_CUSTOM', 'SKIP_NONSTANDARD']:
            if self._matches_policy(policy, row):
                rule = POLICY_RULES[policy]
                return True, rule['description']

        return False, ''

    def _determine_policy(self, row: dict, ev: Evidence) -> str:
        """품목 유형 정책 결정"""
        # 우선순위 순서대로 체크
        for policy in POLICY_PRIORITY:
            if policy.startswith('SKIP'):
                continue
            if self._matches_policy(policy, row):
                return policy

        return 'GENERIC'

    def _matches_policy(self, policy: str, row: dict) -> bool:
        """해당 정책 키워드가 행에 있는지 확인"""
        if policy not in POLICY_RULES:
            return False

        rule = POLICY_RULES[policy]
        keywords = rule['keywords']
        check_fields = rule['fields']

        # 검사 대상 텍스트 수집
        texts = []
        field_map = {
            '품명': row.get('품명', ''),
            'SPEC': row.get('SPEC', ''),
            '제조사': row.get('제조사', ''),
            '대분류': row.get('대분류', ''),
            '메모': row.get('메모', ''),
            '고객주문사유': row.get('고객주문사유', ''),
        }
        for field in check_fields:
            if field in field_map:
                texts.append(str(field_map[field]).lower())

        combined = ' '.join(texts)

        return any(kw.lower() in combined for kw in keywords)