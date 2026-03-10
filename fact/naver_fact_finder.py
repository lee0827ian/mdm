"""
NaverFactFinder
- 네이버 쇼핑 API로 제품 팩트 확인 (가격 제외)
- 모델명 / 제조사 / 브랜드 후보 추출만
- 조건부 호출: 내부 증거 부족할 때만
"""

import os
import re
import json
import time
import random
import requests
from dotenv import load_dotenv

load_dotenv()


class NaverFactFinder:

    API_URL = 'https://openapi.naver.com/v1/search/shop.json'

    def __init__(self, logger=None):
        self.client_id     = os.getenv('NAVER_CLIENT_ID', '')
        self.client_secret = os.getenv('NAVER_CLIENT_SECRET', '')
        self.logger = logger
        self._available = bool(self.client_id and self.client_secret)

    def is_available(self) -> bool:
        return self._available

    def find(self, ev, policy: str) -> dict:
        """
        Evidence 기반으로 네이버 검색 실행
        반환: {
            success, maker_candidates, model_candidates,
            brand_candidates, evidence_titles, source, confidence
        }
        """
        if not self._available:
            return self._empty_result('API키 없음')

        query = self._build_query(ev, policy)
        if not query:
            return self._empty_result('검색어 생성 실패')

        if self.logger:
            self.logger.info(f"  네이버 검색: {query}")

        time.sleep(random.uniform(0.3, 0.8))

        try:
            headers = {
                'X-Naver-Client-Id':     self.client_id,
                'X-Naver-Client-Secret': self.client_secret,
            }
            params = {'query': query, 'display': 5, 'sort': 'sim'}
            resp = requests.get(
                self.API_URL, headers=headers,
                params=params, timeout=5
            )

            if resp.status_code != 200:
                return self._empty_result(f'API오류({resp.status_code})')

            data = resp.json()
            items = data.get('items', [])
            if not items:
                return self._empty_result('검색결과 없음')

            return self._extract_facts(items, query)

        except Exception as e:
            return self._empty_result(f'예외({str(e)[:30]})')

    def _build_query(self, ev, policy: str) -> str:
        """
        검색어 생성 - 우선순위 기반
        1. 모델명 후보 있으면: 브랜드/품명 + 모델명
        2. 모델명 없고 브랜드 단서 있으면: 브랜드 + 품명 + 핵심규격
        3. URL/메모에 코드가 있으면: 추출코드 + 품명
        """
        # 모델명 후보
        model = ev.get_top_model()
        name  = ev.get_top_name()
        maker = ev.get_top_maker()

        if model and len(model) >= 3:
            parts = []
            if maker and len(maker) <= 20:
                parts.append(maker)
            parts.append(model)
            return ' '.join(parts)

        # 모델 없음 - 품명 + 규격 조합
        if name:
            parts = [name]
            spec = ev.parsed_spec
            size = spec.get('size', '')
            mat  = spec.get('material', '')
            if mat:
                parts.append(mat)
            if size:
                parts.append(size)
            return ' '.join(parts[:3])

        return ''

    def _extract_facts(self, items: list, query: str) -> dict:
        """검색 결과에서 팩트 추출"""
        maker_candidates  = []
        model_candidates  = []
        brand_candidates  = []
        evidence_titles   = []

        for item in items[:5]:
            title  = self._clean_html(item.get('title', ''))
            brand  = item.get('brand', '').strip()
            maker  = item.get('maker', '').strip()
            # 가격 필드는 완전히 무시

            if title:
                evidence_titles.append(title)

            if brand and brand not in brand_candidates:
                brand_candidates.append(brand)
                if brand not in maker_candidates:
                    maker_candidates.append(brand)

            if maker and maker not in maker_candidates:
                maker_candidates.append(maker)

            # 제목에서 모델번호 패턴 추출
            model_from_title = self._extract_model_from_title(title, query)
            if model_from_title and model_from_title not in model_candidates:
                model_candidates.append(model_from_title)

        if not any([maker_candidates, model_candidates, brand_candidates]):
            return self._empty_result('유효 팩트 없음')

        # 내부 증거와 일치 여부로 confidence 결정
        confidence = 'inferred'

        return {
            'success':          True,
            'maker_candidates': maker_candidates,
            'model_candidates': model_candidates,
            'brand_candidates': brand_candidates,
            'evidence_titles':  evidence_titles[:3],
            'source':           'naver',
            'confidence':       confidence,
        }

    def _extract_model_from_title(self, title: str, query: str) -> str:
        """제목에서 모델번호 추출"""
        # 영문+숫자 조합 패턴 (모델번호 특징)
        patterns = [
            r'\b([A-Z]{1,4}[\-]?\d{3,}[A-Z0-9\-]*)\b',
            r'\b([A-Za-z0-9]{2,4}[\-]\d{2,}[A-Za-z0-9\-]*)\b',
        ]
        for pattern in patterns:
            m = re.search(pattern, title)
            if m:
                candidate = m.group(1)
                # 쿼리 단어와 겹치는 게 있으면 모델번호일 가능성 높음
                query_tokens = set(query.upper().split())
                if candidate.upper() in query_tokens:
                    return candidate
                if len(candidate) >= 5:
                    return candidate
        return ''

    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거"""
        return re.sub(r'<[^>]+>', '', text).strip()

    def _empty_result(self, reason: str = '') -> dict:
        return {
            'success':          False,
            'maker_candidates': [],
            'model_candidates': [],
            'brand_candidates': [],
            'evidence_titles':  [],
            'source':           'naver',
            'confidence':       'unresolved',
            'reason':           reason,
        }