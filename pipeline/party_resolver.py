"""
[5] PartyResolver (구 BrandClassifier 확장)
- 제조사 / 브랜드 / 스토어 구분
- party_type: manufacturer / brand / store_generic / unknown
"""

import re
from config import STORE_KEYWORDS, KNOWN_MANUFACTURERS
from utils.text_utils import simplify_company_name


class PartyResolver:

    def resolve(self, maker_value: str, brand_value: str = '',
                urls: list = None) -> dict:
        """
        제조사/브랜드 주체 판별
        반환: {maker, brand, seller, party_type, confidence}
        """
        urls = urls or []

        if not maker_value:
            return self._unknown_result()

        party_type = self._classify_party(maker_value)
        simplified = simplify_company_name(maker_value)

        if party_type == 'manufacturer':
            return {
                'maker': simplified or maker_value,
                'brand': brand_value or simplified or maker_value,
                'seller': '',
                'party_type': 'manufacturer',
                'confidence': 'high',
            }

        if party_type == 'store_generic':
            return {
                'maker': '시중품',
                'brand': simplified or maker_value,
                'seller': simplified or maker_value,
                'party_type': 'store_generic',
                'confidence': 'medium',
            }

        # unknown - URL 힌트로 보완
        if urls:
            from utils.domain_utils import get_store_hint, is_marketplace
            for url in urls:
                hint = get_store_hint(url)
                if hint.get('type') == 'manufacturer':
                    return {
                        'maker': hint['name'],
                        'brand': hint['name'],
                        'seller': '',
                        'party_type': 'manufacturer',
                        'confidence': 'medium',
                    }

        return {
            'maker': maker_value,
            'brand': brand_value or maker_value,
            'seller': '',
            'party_type': 'unknown',
            'confidence': 'low',
        }

    def _classify_party(self, name: str) -> str:
        """주체 유형 분류"""
        if not name:
            return 'unknown'

        name_lower = name.lower()
        name_upper = name.upper()

        # 알려진 제조사
        for mfg in KNOWN_MANUFACTURERS:
            if mfg.lower() in name_lower:
                return 'manufacturer'

        # 스토어/판매처 키워드
        if any(kw in name_lower for kw in STORE_KEYWORDS):
            return 'store_generic'

        # 개인 스토어 패턴 (숫자+이름 조합, 짧은 이름)
        if re.search(r'^\d+$', name.strip()):
            return 'store_generic'

        # 정식 법인명 패턴 → 제조사 가능성
        if any(suffix in name for suffix in ['(주)', '㈜', '주식회사', '(유)', 'Inc', 'Corp', 'Ltd', 'Co.']):
            return 'manufacturer'

        return 'unknown'

    def _unknown_result(self) -> dict:
        return {
            'maker': '',
            'brand': '',
            'seller': '',
            'party_type': 'unknown',
            'confidence': 'low',
        }