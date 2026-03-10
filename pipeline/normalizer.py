"""
[1] RawInputNormalizer
- placeholder 제거
- 전각/반각 통일
- 엑셀 숫자 모델명 보정
- 중복 컬럼 정리
- 컬럼 alias 매핑
"""

import re
import pandas as pd
from config import COLUMN_ALIASES, PLACEHOLDER_VALUES
from utils.text_utils import clean_value, normalize_text, fix_numeric_model


class RawInputNormalizer:

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """전체 데이터프레임 정규화"""
        df = self._align_columns(df)
        df = self._clean_values(df)
        df = self._fix_model_numbers(df)
        return df

    def normalize_row(self, row: dict) -> dict:
        """단일 행 정규화"""
        result = {}
        for key, val in row.items():
            cleaned = clean_value(val)
            normalized = normalize_text(cleaned)
            result[key] = normalized

        # 모델명 숫자 보정
        if '모델명' in result:
            result['모델명'] = fix_numeric_model(result['모델명'])
        if '최초모델명' in result:
            result['최초모델명'] = fix_numeric_model(result['최초모델명'])

        return result

    def _align_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """컬럼 alias 매핑 - 표준 컬럼명으로 통일"""
        for std_col, aliases in COLUMN_ALIASES.items():
            if std_col not in df.columns:
                for alias in aliases:
                    if alias in df.columns:
                        df[std_col] = df[alias]
                        break
            # 없으면 빈 컬럼 생성
            if std_col not in df.columns:
                df[std_col] = ''

        # 중복 컬럼 처리 (같은 이름이 두 번 나오는 경우)
        df = df.loc[:, ~df.columns.duplicated(keep='first')]

        return df

    def _clean_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """전체 값 정제"""
        for col in df.columns:
            df[col] = df[col].apply(lambda x: clean_value(x))
            df[col] = df[col].apply(lambda x: normalize_text(x))
        return df

    def _fix_model_numbers(self, df: pd.DataFrame) -> pd.DataFrame:
        """엑셀 숫자 모델명 보정"""
        for col in ['모델명', '최초모델명']:
            if col in df.columns:
                df[col] = df[col].apply(fix_numeric_model)
        return df

    def get_standard_columns(self) -> list:
        """표준 컬럼 목록 반환"""
        return list(COLUMN_ALIASES.keys())