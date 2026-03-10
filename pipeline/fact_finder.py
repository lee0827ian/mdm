"""
[6] FactFinder - 조건부 외부 팩트 수집
- 내부 증거 부족할 때만 호출
- ProductPageFactFinder (URL 크롤링) 우선
- NaverFactFinder (네이버 검색) 보조
"""

from models.evidence import Evidence
from fact.page_fact_finder import ProductPageFactFinder
from fact.naver_fact_finder import NaverFactFinder
from config import FACT_FINDER_TRIGGER


class FactFinder:

    def __init__(self, logger=None):
        self.page_finder  = ProductPageFactFinder(logger=logger)
        self.naver_finder = NaverFactFinder(logger=logger)
        self.logger = logger

    def should_run(self, ev: Evidence, policy: str) -> tuple:
        """
        FactFinder 호출 필요 여부 판단
        반환: (실행여부: bool, 사유: str)
        """
        maker_missing = not ev.get_top_maker() or ev.get_top_maker() in ('--', '-', '시중품')
        model_missing = not ev.get_top_model() or ev.get_top_model() in ('--', '-')

        # 제조사 없음
        if FACT_FINDER_TRIGGER.get('maker_missing') and maker_missing:
            return True, 'maker_missing'

        # 모델명 없음 (MODEL_CENTERED 정책일 때)
        if FACT_FINDER_TRIGGER.get('model_missing') and model_missing:
            if policy == 'MODEL_CENTERED':
                return True, 'model_missing (MODEL_CENTERED)'

        # 현재값/최초값 충돌
        if FACT_FINDER_TRIGGER.get('conflict'):
            maker_conflict = (
                len([v for v, s in ev.maker_candidates
                     if s in ('current', 'first_info')]) >= 2
                and len(set(v for v, s in ev.maker_candidates
                            if s in ('current', 'first_info'))) > 1
            )
            if maker_conflict:
                return True, 'maker_conflict'

        return False, ''

    def run(self, ev: Evidence, policy: str) -> dict:
        """
        팩트 수집 실행
        URL 크롤링 → 네이버 검색 순서
        """
        should, reason = self.should_run(ev, policy)
        if not should:
            return {'success': False, 'reason': 'trigger_not_met'}

        if self.logger:
            self.logger.info(f"  FactFinder 실행: {reason}")

        # 1순위: URL 크롤링
        if ev.has_url():
            crawlable = [u for u in ev.urls]
            result = self.page_finder.find(crawlable)
            if result['success']:
                if self.logger:
                    self.logger.info(f"  PageFact 성공: {result['maker_candidates']}")
                return result

        # 2순위: 네이버 검색
        if self.naver_finder.is_available():
            result = self.naver_finder.find(ev, policy)
            if result['success']:
                if self.logger:
                    self.logger.info(f"  NaverFact 성공: {result['maker_candidates']}")
                return result

        return {'success': False, 'reason': 'no_fact_found'}