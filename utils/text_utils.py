"""
텍스트 정제 유틸리티
- 전각/반각 통일
- placeholder 제거
- 특수문자 정리
"""

import re
from config import PLACEHOLDER_VALUES


def is_placeholder(value: str) -> bool:
    """공란/placeholder 여부 확인"""
    if value is None:
        return True
    return str(value).strip().lower() in PLACEHOLDER_VALUES


def clean_value(value) -> str:
    """기본 정제: None/placeholder → 공란, 앞뒤 공백 제거"""
    if value is None:
        return ''
    v = str(value).strip()
    if v.lower() in PLACEHOLDER_VALUES:
        return ''
    return v


def normalize_text(text: str) -> str:
    """
    텍스트 정규화
    - 전각 → 반각
    - 연속 공백 축소
    - 줄바꿈 → 공백
    """
    if not text:
        return ''

    # 전각 → 반각
    result = ''
    for char in text:
        code = ord(char)
        if 0xFF01 <= code <= 0xFF5E:
            result += chr(code - 0xFEE0)
        elif char == '\u3000':  # 전각 공백
            result += ' '
        else:
            result += char

    # 줄바꿈 → 공백
    result = result.replace('\n', ' ').replace('\r', ' ')

    # 연속 공백 축소
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def fix_numeric_model(value: str) -> str:
    """
    엑셀에서 숫자로 읽힌 모델명 보정
    예: '12345.0' → '12345'
    """
    if re.fullmatch(r'\d+\.0', value.strip()):
        return value.strip().split('.')[0]
    return value


def remove_noise_patterns(text: str, patterns: list) -> str:
    """노이즈 패턴 제거"""
    result = text
    for pattern in patterns:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    # 남은 연속 쉼표/공백 정리
    result = re.sub(r',\s*,', ',', result)
    result = re.sub(r'^\s*,|,\s*$', '', result)
    return result.strip()


def extract_bracket_content(text: str) -> list:
    """
    대괄호 내용 추출
    예: '[SIZE:4IN][MATERIAL:A105]' → ['SIZE:4IN', 'MATERIAL:A105']
    """
    return re.findall(r'\[([^\]]+)\]', text)


def split_key_value(text: str) -> dict:
    """
    키:값 형태 텍스트 파싱
    예: 'Maker: YAMAWA, Model: TNPT01L, 규격: 1/16-27'
    → {'Maker': 'YAMAWA', 'Model': 'TNPT01L', '규격': '1/16-27'}
    """
    result = {}
    # 쉼표 또는 줄바꿈으로 분리
    parts = re.split(r'[,\n]', text)
    for part in parts:
        m = re.match(r'\s*([^:]+?)\s*:\s*(.+)', part.strip())
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key and val:
                result[key] = val
    return result


def normalize_model_name(model: str) -> str:
    """
    모델명 정규화
    - NAVI 코드 제거
    - 앞뒤 공백 제거
    """
    if not model:
        return ''
    model = re.sub(r'K\d+\(NAVI\)', '', model)
    model = re.sub(r'\([^)]*NAVI[^)]*\)', '', model)
    return model.strip()


def simplify_company_name(name: str) -> str:
    """
    회사명 간소화
    예: '(주)더스마티' → '더스마티', '주식회사 SMC' → 'SMC'
    """
    if not name:
        return ''
    name = re.sub(r'\([^)]*\)', '', name)
    name = name.replace('주식회사', '').replace('(주)', '').replace('㈜', '')
    name = name.replace('유한회사', '').replace('유한책임회사', '')
    name = name.replace('(유)', '').replace('주식회사', '')
    return name.strip()


def tokenize_korean(text: str) -> list:
    """한글/영문/숫자 2글자 이상 토큰 추출"""
    return re.findall(r'[가-힣a-zA-Z0-9]{2,}', text)