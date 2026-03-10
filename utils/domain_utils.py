"""
도메인 → 스토어명/제조사 힌트 매핑
"""

from urllib.parse import urlparse


# 도메인 → 스토어/제조사 힌트
DOMAIN_STORE_MAP = {
    'smartstore.naver.com': ('스마트스토어', 'store'),
    'brand.naver.com':      ('네이버브랜드스토어', 'brand'),
    'shopping.naver.com':   ('네이버쇼핑', 'marketplace'),
    'coupang.com':          ('쿠팡', 'marketplace'),
    '11st.co.kr':           ('11번가', 'marketplace'),
    'gmarket.co.kr':        ('G마켓', 'marketplace'),
    'auction.co.kr':        ('옥션', 'marketplace'),
    'ssg.com':              ('SSG', 'marketplace'),
    'lotteon.com':          ('롯데온', 'marketplace'),
    'interpark.com':        ('인터파크', 'marketplace'),
    'tmon.co.kr':           ('티몬', 'marketplace'),
    'wemakeprice.com':      ('위메프', 'marketplace'),
    # B2B/전문몰
    'misumi-ec.com':        ('미스미', 'manufacturer'),
    'kr.misumi-ec.com':     ('미스미', 'manufacturer'),
    'monotaro.com':         ('모노타로', 'store'),
    'navimro.com':          ('나비MRO', 'store'),
    'hit10.co.kr':          ('hit10', 'store'),
    'ledmk.co.kr':          ('ledmk', 'store'),
    # 제조사 공식몰
    'apple.com':            ('Apple', 'manufacturer'),
    'samsung.com':          ('Samsung', 'manufacturer'),
    'lg.com':               ('LG', 'manufacturer'),
    'smc.co.kr':            ('SMC', 'manufacturer'),
    'item.gmarket.co.kr':   ('G마켓', 'marketplace'),
}

# 차단 도메인 (크롤링 불가)
BLOCKED_CRAWL_DOMAINS = {
    'smartstore.naver.com',
    'brand.naver.com',
    'shopping.naver.com',
    'coupang.com',
    'www.coupang.com',
    '11st.co.kr',
    'www.11st.co.kr',
    'gmarket.co.kr',
    'auction.co.kr',
    'tmon.co.kr',
    'wemakeprice.com',
    'ssg.com',
    'lotteon.com',
    'interpark.com',
}


def extract_domain(url: str) -> str:
    """URL에서 도메인 추출"""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ''
    except Exception:
        return ''


def get_store_hint(url: str) -> dict:
    """
    URL에서 스토어/제조사 힌트 추출
    반환: {'name': str, 'type': str, 'domain': str}
    """
    domain = extract_domain(url)
    if not domain:
        return {}

    # 전체 도메인 매칭
    if domain in DOMAIN_STORE_MAP:
        name, dtype = DOMAIN_STORE_MAP[domain]
        return {'name': name, 'type': dtype, 'domain': domain}

    # www. 제거 후 재시도
    domain_no_www = domain.replace('www.', '')
    if domain_no_www in DOMAIN_STORE_MAP:
        name, dtype = DOMAIN_STORE_MAP[domain_no_www]
        return {'name': name, 'type': dtype, 'domain': domain}

    # 도메인에서 브랜드명 추정 (첫 번째 파트)
    parts = domain_no_www.split('.')
    if parts:
        return {'name': parts[0], 'type': 'unknown', 'domain': domain}

    return {'name': domain, 'type': 'unknown', 'domain': domain}


def is_blocked_domain(url: str) -> bool:
    """크롤링 차단 도메인 여부"""
    domain = extract_domain(url)
    domain_no_www = domain.replace('www.', '')
    return domain in BLOCKED_CRAWL_DOMAINS or domain_no_www in BLOCKED_CRAWL_DOMAINS


def is_marketplace(url: str) -> bool:
    """오픈마켓/마켓플레이스 여부"""
    hint = get_store_hint(url)
    return hint.get('type') == 'marketplace'