"""
URL 추출기
- 텍스트 전체에서 URL 추출
- 도메인에서 스토어/브랜드 힌트 추출
"""

import re
from utils.domain_utils import get_store_hint, is_blocked_domain, is_marketplace


# URL 추출 정규식
URL_PATTERN = re.compile(
    r'https?://'
    r'[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'
    r'(?<![.,)\s])',
    re.IGNORECASE
)


class URLExtractor:

    def extract_urls(self, text: str) -> list:
        """텍스트에서 URL 목록 추출"""
        if not text:
            return []
        urls = URL_PATTERN.findall(text)
        # 중복 제거, 순서 유지
        seen = set()
        result = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                result.append(url)
        return result

    def extract_from_fields(self, row: dict) -> list:
        """
        여러 컬럼에서 URL 추출
        우선순위: 메모 > 고객주문사유 > 고객전체사유 > SPEC > 최초규격
        """
        fields = [
            row.get('메모', ''),
            row.get('고객주문사유', ''),
            row.get('고객전체사유', ''),
            row.get('SPEC', ''),
            row.get('최초규격', ''),
        ]

        seen = set()
        result = []
        for field in fields:
            for url in self.extract_urls(str(field)):
                if url not in seen:
                    seen.add(url)
                    result.append(url)
        return result

    def get_url_hints(self, urls: list) -> list:
        """
        URL 목록에서 스토어/브랜드 힌트 추출
        반환: [{'url': str, 'store': str, 'type': str, 'crawlable': bool}, ...]
        """
        hints = []
        for url in urls:
            hint = get_store_hint(url)
            crawlable = not is_blocked_domain(url)
            hints.append({
                'url': url,
                'store': hint.get('name', ''),
                'type': hint.get('type', 'unknown'),
                'domain': hint.get('domain', ''),
                'crawlable': crawlable,
                'is_marketplace': is_marketplace(url),
            })
        return hints

    def get_crawlable_urls(self, urls: list) -> list:
        """크롤링 가능한 URL만 반환"""
        return [u for u in urls if not is_blocked_domain(u)]

    def extract_store_names(self, urls: list) -> list:
        """URL에서 스토어명 후보 추출"""
        names = []
        for url in urls:
            hint = get_store_hint(url)
            name = hint.get('name', '')
            dtype = hint.get('type', '')
            if name and dtype not in ('marketplace',):
                names.append((name, f'url_domain'))
        return names