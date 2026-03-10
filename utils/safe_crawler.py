"""
IP 안전 크롤러 (v13.4 SafeCrawler 계승)
- 랜덤 딜레이
- User-Agent 로테이션
- 도메인 health 추적
"""

import re
import random
import time
import requests
import urllib3
from bs4 import BeautifulSoup
from collections import defaultdict
from urllib.parse import urlparse
from utils.domain_utils import is_blocked_domain

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
]

BLOCKED_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.zip', '.rar', '.hwp',
]


class SafeCrawler:
    """IP 안전 웹 크롤러"""

    def __init__(self, delay_range=(1.0, 2.5), logger=None):
        self.delay_range = delay_range
        self.logger = logger
        self.domain_health = defaultdict(lambda: {'fails': 0})

    def can_fetch(self, url: str) -> tuple:
        """
        크롤링 가능 여부 확인
        반환: (가능여부: bool, 사유: str)
        """
        if not url or not url.startswith('http'):
            return False, 'URL없음'

        url_lower = url.lower()

        # 차단 확장자
        for ext in BLOCKED_EXTENSIONS:
            if ext in url_lower:
                return False, f'문서파일({ext})'

        # 차단 도메인
        if is_blocked_domain(url):
            domain = urlparse(url).hostname or ''
            return False, f'차단도메인({domain})'

        # 도메인 health
        domain = urlparse(url).hostname or ''
        if self.domain_health[domain]['fails'] >= 3:
            return False, f'도메인불안정({self.domain_health[domain]["fails"]}회실패)'

        return True, 'OK'

    def fetch(self, url: str, timeout=7) -> dict:
        """
        URL 페이지 가져오기
        반환: {'success': bool, 'html': str, 'reason': str}
        """
        domain = urlparse(url).hostname or ''

        try:
            time.sleep(random.uniform(*self.delay_range))

            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }

            resp = requests.get(
                url, headers=headers,
                timeout=timeout, verify=False,
                allow_redirects=True,
            )

            if resp.status_code == 403:
                self.domain_health[domain]['fails'] += 2
                return {'success': False, 'html': '', 'reason': '403차단'}

            if resp.status_code != 200:
                self.domain_health[domain]['fails'] += 1
                return {'success': False, 'html': '', 'reason': f'HTTP{resp.status_code}'}

            # 성공 시 fail 카운트 감소
            self.domain_health[domain]['fails'] = max(
                0, self.domain_health[domain]['fails'] - 1
            )

            return {'success': True, 'html': resp.text, 'reason': 'OK'}

        except requests.exceptions.Timeout:
            self.domain_health[domain]['fails'] += 1
            return {'success': False, 'html': '', 'reason': '타임아웃'}

        except requests.exceptions.ConnectionError:
            self.domain_health[domain]['fails'] += 1
            return {'success': False, 'html': '', 'reason': '연결실패'}

        except Exception as e:
            return {'success': False, 'html': '', 'reason': f'오류({str(e)[:30]})'}

    def extract_product_info(self, html: str) -> dict:
        """
        HTML에서 제품 정보 추출 (가격 제외)
        반환: {
            'title': str,
            'brand': str,
            'model': str,
            'description': str,
        }
        """
        result = {'title': '', 'brand': '', 'model': '', 'description': ''}

        if not html:
            return result

        soup = BeautifulSoup(html, 'html.parser')

        # og:title
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title:
            result['title'] = og_title.get('content', '').strip()

        # title 태그
        if not result['title']:
            title_tag = soup.find('title')
            if title_tag:
                result['title'] = title_tag.get_text().strip()

        # JSON-LD에서 brand/model
        import json
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        result['model'] = data.get('model', '') or data.get('sku', '')
                        brand = data.get('brand', {})
                        if isinstance(brand, dict):
                            result['brand'] = brand.get('name', '')
                        elif isinstance(brand, str):
                            result['brand'] = brand
                        result['description'] = data.get('description', '')[:200]
                        break
            except Exception:
                continue

        # og:description
        if not result['description']:
            og_desc = soup.select_one('meta[property="og:description"]')
            if og_desc:
                result['description'] = og_desc.get('content', '')[:200]

        return result

    def get_page_text(self, html: str, max_chars=2000) -> str:
        """HTML에서 본문 텍스트 추출"""
        if not html:
            return ''
        soup = BeautifulSoup(html, 'html.parser')
        # script, style 제거
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        text = soup.get_text(' ', strip=True)
        return re.sub(r'\s+', ' ', text)[:max_chars]