"""
영문 품명 → 한글 표준품명 변환 (최소 규칙 기반)
확실한 것만 하드코딩, 나머지는 FactFinder로 처리
"""

# 영문 → 한글 표준품명
PRODUCT_NAME_MAP = {
    # 배관 피팅류
    'BOLT STUD':            '스터드볼트',
    'STUD BOLT':            '스터드볼트',
    'PLAIN GASKET':         '가스켓',
    'SPIRAL WOUND GASKET':  '가스켓',
    'FULL COUPLING':        '풀커플링',
    'HALF COUPLING':        '하프커플링',
    'ELBOW':                '엘보',
    'HEX UNION':            '유니온',
    'UNION':                '유니온',
    'NIPPLE':               '니플',
    'SEAMLESS NIPPLE':      '니플',
    'CONNECTOR':            '커넥터',
    'REDUCER':              '리듀서',
    'TEE':                  '티',
    'FLANGE':               '플랜지',
    # 씰류
    'O-RING':               'O링',
    'O RING':               'O링',
    'ORING':                'O링',
    'DIAPHRAGM':            '다이어프램',
    'PACKING':              '패킹',
    # 기타 기계
    'WASHER':               '와셔',
    'GASKET':               '가스켓',
    'RING':                 '링',
    'VALVE':                '밸브',
    'PUMP':                 '펌프',
    'MOTOR':                '모터',
    # IT/전자
    'NOTEBOOK':             '노트북',
    'MONITOR':              '모니터',
    'MONITORING DEVICE':    '모니터',
    'PLATFORM_MOBILELAB':   '노트북',
    # 계측
    'ACCELEROMETER':        '가속도센서',
    'PROXIMITY SENSOR':     '근접센서',
    'SIGNAL CONDITIONAL':   '신호변환기',
    # 기타
    'LAMP':                 '램프',
    'COOLING FAN':          '쿨링팬',
    'FLEXIBLE HOSE':        '플렉시블호스',
}

# 품명 앞에 붙는 노이즈 패턴 제거
# 예: "BOLT STUD(RC-E4006)" → "BOLT STUD"
PRODUCT_NAME_NOISE_PATTERNS = [
    r'\([A-Z0-9\-_]+\)$',          # 끝의 괄호 코드 제거
    r'_[A-Z0-9\-_ ]+$',            # 언더스코어 뒤 코드 제거
    r'^\s*OTHER\s+INSTRUMENT\s+ACCESSORY\s*$',  # 무의미 품명
    r'^\s*OTHERS?\s*$',
    r'^\s*-+\s*$',
]


def normalize_product_name(raw_name: str) -> str:
    """
    품명 정규화
    1. 노이즈 패턴 제거
    2. 영문 → 한글 표준품명 변환
    3. 변환 불가 시 원본 반환
    """
    import re

    if not raw_name:
        return ''

    name = raw_name.strip()

    # 노이즈 제거
    for pattern in PRODUCT_NAME_NOISE_PATTERNS:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()

    if not name:
        return raw_name.strip()

    # 영문 → 한글 변환 (대소문자 무관)
    name_upper = name.upper()
    for eng, kor in PRODUCT_NAME_MAP.items():
        if name_upper.startswith(eng.upper()):
            return kor

    return name