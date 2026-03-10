"""
ProductPageFactFinder
- URL 크롤링으로 제품 정보 추출
- 가격 제외, 제조사/모델명/브랜드만 수집
"""

import re
from utils.safe_crawler import SafeCrawler
from utils.domain_utils import is_blocked_domain


class ProductPageFactFinder:

    def __init__(self, logger=None):
        self.crawler = SafeCrawler(delay_range=(1.0, 2.0), logger=logger)
        self.logger = logger

    def find(self, urls: list) -> dict:
        """
        URL 목록에서 제품 팩트 수집
        크롤링 가능한 URL만 시도, 첫 번째 성공 결과 반환
        반환: {
            success, maker_candidates, model_candidates,
            brand_candidates, evidence_titles, source, confidence
        }
        """
        for url in urls:
            if is_blocked_domain(url):
                continue

            ok, reason = self.crawler.can_fetch(url)
            if not ok:
                if self.logger:
                    self.logger.info(f"  URL 스킵: {reason} ({url[:60]})")
                continue

            if self.logger:
                self.logger.info(f"  URL 크롤링: {url[:60]}")

            fetch_result = self.crawler.fetch(url)
            if not fetch_result['success']:
                if self.logger:
                    self.logger.info(f"  크롤링 실패: {fetch_result['reason']}")
                continue

            product_info = self.crawler.extract_product_info(fetch_result['html'])
            page_text    = self.crawler.get_page_text(fetch_result['html'])

            result = self._extract_facts(product_info, page_text, url)
            if result['success']:
                return result

        return self._empty_result()

    def _extract_facts(self, product_info: dict, page_text: str, url: str) -> dict:
        """크롤링 결과에서 팩트 추출"""
        maker_candidates  = []
        model_candidates  = []
        brand_candidates  = []
        evidence_titles   = []

        title = product_info.get('title', '')
        brand = product_info.get('brand', '')
        model = product_info.get('model', '')
        desc  = product_info.get('description', '')

        if title:
            evidence_titles.append(title)

        # 브랜드
        if brand:
            brand_candidates.append(brand)
            maker_candidates.append(brand)

        # 모델명
        if model:
            model_candidates.append(model)

        # 텍스트에서 추가 추출
        if page_text:
            extracted = self._extract_from_text(page_text)
            model_candidates.extend(extracted.get('models', []))
            maker_candidates.extend(extracted.get('makers', []))

        # 최소 하나라도 있어야 성공
        if not any([maker_candidates, model_candidates, brand_candidates, title]):
            return self._empty_result()

        # 중복 제거
        maker_candidates  = list(dict.fromkeys([m for m in maker_candidates if m]))
        model_candidates  = list(dict.fromkeys([m for m in model_candidates if m]))
        brand_candidates  = list(dict.fromkeys([b for b in brand_candidates if b]))

        return {
            'success':          True,
            'maker_candidates': maker_candidates,
            'model_candidates': model_candidates,
            'brand_candidates': brand_candidates,
            'evidence_titles':  evidence_titles,
            'source':           'page',
            'confidence':       'inferred',
        }

    def _extract_from_text(self, text: str) -> dict:
        """페이지 텍스트에서 제조사/모델명 패턴 추출"""
        result = {'models': [], 'makers': []}

        # 모델번호 패턴
        model_patterns = [
            r'모델\s*번호?\s*[:：]\s*([A-Za-z0-9\-_]+)',
            r'Model\s*(?:No\.?)?\s*[:：]\s*([A-Za-z0-9\-_]+)',
            r'품번\s*[:：]\s*([A-Za-z0-9\-_]+)',
        ]
        for pattern in model_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                result['models'].append(m.group(1).strip())

        # 제조사 패턴
        maker_patterns = [
            r'제조(?:사|업체|원)\s*[:：]\s*([가-힣a-zA-Z0-9\(\)주식회사(주)㈜ ]+)',
            r'브랜드\s*[:：]\s*([가-힣a-zA-Z0-9 ]+)',
            r'Manufacturer\s*[:：]\s*([A-Za-z0-9 ]+)',
        ]
        for pattern in maker_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().split('\n')[0][:30]
                result['makers'].append(val)

        return result

    def _empty_result(self) -> dict:
        return {
            'success':          False,
            'maker_candidates': [],
            'model_candidates': [],
            'brand_candidates': [],
            'evidence_titles':  [],
            'source':           'page',
            'confidence':       'unresolved',
        }