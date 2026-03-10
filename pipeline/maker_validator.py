"""
[11] MakerValidator
- 결정된 제조사가 표준 허용 목록(std_maker)에 있는지 검증
- 유사 제조사명 후보 제시 (퍼지 매칭)
- alias/원문 context 기반으로 외부팩트 오판정 완화
"""

from __future__ import annotations

import re
from models.resolved_field import ResolvedField
from standards.db_loader import StandardDBLoader


class MakerValidator:
    SKIP_VALUES = {'시중품', '', '--', '-', '해당없음', 'N/A'}

    MAKER_ALIASES = {
        '밀워키': 'MILWAUKEE',
        '디월트': 'DEWALT',
        '마끼다': 'MAKITA',
        '보쉬': 'BOSCH',
        '삼성': '삼성전자',
        'HP': 'HEWLETT PACKARD(HP)',
        'LG': 'LG전자',
        '미스미': 'MISUMI',
        'ebmpapst': 'EBM-PAPST',
        '폼텍': '한국폼텍',
    }

    def __init__(self, db_loader: StandardDBLoader):
        self.db = db_loader
        self._maker_cache: list[dict] = []
        self._maker_names: list[str] = []
        self._load_maker_cache()

    def _load_maker_cache(self):
        rows = self.db._conn.execute(
            "SELECT 표준제조사명, 영문명, 제조사코드, 취급품목 FROM std_maker"
        ).fetchall()
        self._maker_cache = [dict(r) for r in rows]
        self._maker_names = [r['표준제조사명'] for r in self._maker_cache]
        print(f"[MakerValidator] 제조사 {len(self._maker_names):,}개 캐시 완료")

    def validate(self, maker_field: ResolvedField, context_text: str = '') -> dict:
        value = (maker_field.value or '').strip()

        if value in self.SKIP_VALUES:
            return self._skip_result(value)

        # 1) exact
        exact = self._exact_match(value)
        if exact:
            return {
                'is_standard': True,
                'matched_name': exact['표준제조사명'],
                'matched_item': exact,
                'candidates': [],
                'flag': False,
                'method': 'exact',
                'confidence': 'high',
            }

        # 2) alias exact
        alias = self.MAKER_ALIASES.get(value, '')
        if alias:
            alias_match = self._exact_match(alias)
            if alias_match:
                return {
                    'is_standard': True,
                    'matched_name': alias_match['표준제조사명'],
                    'matched_item': alias_match,
                    'candidates': [],
                    'flag': False,
                    'method': 'alias',
                    'confidence': 'high',
                }

        # 3) normalized
        normalized = self._normalize_maker(value)
        norm_match = self._exact_match(normalized)
        if norm_match:
            return {
                'is_standard': True,
                'matched_name': norm_match['표준제조사명'],
                'matched_item': norm_match,
                'candidates': [],
                'flag': False,
                'method': 'normalized',
                'confidence': 'medium',
            }

        # 4) fuzzy + context
        candidates = self._fuzzy_candidates(value, context_text=context_text, top_n=3)

        # top1이 충분히 강하면 자동 매핑 후보 제공
        if candidates and candidates[0]['score'] >= 0.75:
            return {
                'is_standard': True,
                'matched_name': candidates[0]['maker_name'],
                'matched_item': candidates[0]['item'],
                'candidates': candidates,
                'flag': False,
                'method': 'fuzzy',
                'confidence': 'medium',
            }

        return {
            'is_standard': False,
            'matched_name': '',
            'matched_item': {},
            'candidates': candidates,
            'flag': True,
            'method': 'none',
            'confidence': 'low',
        }

    def _exact_match(self, name: str) -> dict:
        name_lower = name.lower()
        for item in self._maker_cache:
            if item['표준제조사명'].lower() == name_lower:
                return item
            if item.get('영문명') and item['영문명'].lower() == name_lower:
                return item
        return {}

    @staticmethod
    def _normalize_maker(name: str) -> str:
        name = name.strip()
        name = re.sub(r'^[\(（\[【]?(주|유|합|사단법인|재단법인)[\)）\]】]?\s*', '', name)
        name = re.sub(r'\s*[\(（\[【](주|유|합)[\)）\]】]$', '', name)
        name = re.sub(
            r'\s*(주식회사|유한회사|합자회사|Co\.|Corp\.|Inc\.|Ltd\.|LLC)',
            '', name, flags=re.IGNORECASE
        )
        return name.strip()

    def _fuzzy_candidates(self, name: str, context_text: str = '', top_n: int = 3) -> list[dict]:
        name_lower = name.lower()
        norm_name = self._normalize_maker(name).lower()
        ctx = str(context_text or '').lower()

        scored = []

        for item in self._maker_cache:
            std = item['표준제조사명']
            std_lower = std.lower()
            std_norm = self._normalize_maker(std).lower()

            score = 0.0

            # 포함 관계
            if std_norm and std_norm in norm_name:
                score = max(score, len(std_norm) / max(len(norm_name), 1) + 0.3)
            if norm_name and norm_name in std_norm:
                score = max(score, len(norm_name) / max(len(std_norm), 1) + 0.2)

            # 토큰 교집합
            raw_tokens = set(re.split(r'[\s\-_/,·•()\[\]]+', norm_name))
            std_tokens = set(re.split(r'[\s\-_/,·•()\[\]]+', std_norm))
            raw_tokens = {t for t in raw_tokens if len(t) >= 2}
            std_tokens = {t for t in std_tokens if len(t) >= 2}

            if raw_tokens and std_tokens:
                inter = raw_tokens & std_tokens
                if inter:
                    tok_score = len(inter) / max(len(raw_tokens), len(std_tokens))
                    score = max(score, tok_score)

            # context 가산/감산
            if ctx:
                if std_lower in ctx or std_norm in ctx:
                    score += 0.3
                elif norm_name and norm_name not in ctx and std_norm not in ctx:
                    # context에 전혀 안 보이면 과한 후보를 조금 깎음
                    score -= 0.1

            if score >= 0.4:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                'score': round(s, 2),
                'maker_name': item['표준제조사명'],
                'maker_code': item.get('제조사코드', ''),
                'item': item,
            }
            for s, item in scored[:top_n]
        ]

    @staticmethod
    def _skip_result(value: str) -> dict:
        return {
            'is_standard': True,
            'matched_name': value,
            'matched_item': {},
            'candidates': [],
            'flag': False,
            'method': 'skip',
            'confidence': 'high',
        }
    