"""
MDM 표준화 엔진 v1.1
실행: python main.py
"""

import os
import sys
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path

from pipeline.normalizer import RawInputNormalizer
from pipeline.evidence_collector import EvidenceCollector
from pipeline.policy_router import StandardizationPolicyRouter
from pipeline.fact_finder import FactFinder
from pipeline.field_resolver import StandardFieldResolver
from pipeline.review_flagger import ReviewFlagger
from pipeline.standard_matcher import StandardMatcherStep
from pipeline.attr_validator import AttrValidator
from pipeline.maker_validator import MakerValidator
from standards.db_loader import StandardDBLoader
from models.standard_result import StandardResult
from config import OUTPUT_COLUMNS, LOG_DIR, OUTPUT_DIR, CACHE_DIR


# =============================================================================
# 로깅 설정
# =============================================================================

def setup_logger() -> logging.Logger:
    Path(LOG_DIR).mkdir(exist_ok=True)
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    Path(CACHE_DIR).mkdir(exist_ok=True)

    log_file = os.path.join(LOG_DIR, f"mdm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logger = logging.getLogger('mdm')
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    return logger


# =============================================================================
# 파일 로드
# =============================================================================

def load_input_file(filepath: str) -> pd.DataFrame:
    ext = Path(filepath).suffix.lower()
    if ext == '.xlsx':
        df = pd.read_excel(filepath, dtype=str, engine='calamine')
    elif ext == '.xls':
        df = pd.read_excel(filepath, dtype=str, engine='xlrd')
    elif ext == '.csv':
        df = pd.read_csv(filepath, dtype=str, encoding='utf-8-sig', sep='\t', on_bad_lines='skip', index_col=False)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")
    return df


# =============================================================================
# 결과 저장
# =============================================================================

def save_results(results: list, output_dir: str) -> str:
    rows = [r.to_excel_row() for r in results]
    df_out = pd.DataFrame(rows)

    cols = [c for c in OUTPUT_COLUMNS if c in df_out.columns]
    extra = [c for c in df_out.columns if c not in cols]
    df_out = df_out[cols + extra]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(output_dir, f'표준화결과_{timestamp}.xlsx')

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        df_out.to_excel(writer, index=False, sheet_name='표준화결과')

        ws = writer.sheets['표준화결과']
        for col_idx, col in enumerate(df_out.columns, 1):
            max_len = max(
                df_out[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            ws.column_dimensions[
                ws.cell(1, col_idx).column_letter
            ].width = min(max_len, 40)

    return out_path


# =============================================================================
# 단일 행 처리
# =============================================================================

def process_row(
    row: dict,
    ev_collector: EvidenceCollector,
    policy_router: StandardizationPolicyRouter,
    fact_finder: FactFinder,
    field_resolver: StandardFieldResolver,
    flagger: ReviewFlagger,
    std_matcher: StandardMatcherStep,
    attr_validator: AttrValidator,
    maker_validator: MakerValidator,
    logger: logging.Logger,
) -> StandardResult:

    result = StandardResult(
        관리번호   = row.get('행복나래관리번호', row.get('관리번호', '')),
        원본품명   = row.get('품명', ''),
        원본SPEC   = row.get('SPEC', ''),
        원본제조사 = row.get('제조사', ''),
        원본모델명 = row.get('모델명', ''),
    )

    # ── [2] 증거 수집 ────────────────────────────────────────────────────────
    ev = ev_collector.collect(row)

    # ── [3] 정책 결정 ────────────────────────────────────────────────────────
    policy, skip, skip_reason = policy_router.route(row, ev)

    if skip:
        result.처리가능여부 = False
        result.처리불가사유 = skip_reason
        result.처리정책    = 'SKIP'
        logger.info(f"  처리불가: {skip_reason}")
        return result

    result.처리정책 = policy

    # ── [6] FactFinder (정책별 허용 조건 체크) ───────────────────────────────────
    from config import FACT_FINDER_POLICY_ALLOW
    if FACT_FINDER_POLICY_ALLOW.get(policy, False):
        fact_result = fact_finder.run(ev, policy)
    else:
        fact_result = {'success': False, 'reason': f'policy={policy} FactFinder 비허용'}
        logger.info(f'  [6] FactFinder 스킵 (policy={policy})')

    # ── [7] 표준 필드 결정 ───────────────────────────────────────────────────
    fields = field_resolver.resolve(row, ev, policy, fact_result)

    # ── [9] 표준품명 DB 매핑 ─────────────────────────────────────────────────
    fields['표준품명'] = std_matcher.match(fields['표준품명'], ev, policy=policy)
    logger.info(
        f"  [9] 품명매핑: '{result.원본품명}' → '{fields['표준품명'].value}' "
        f"[{fields['표준품명'].confidence}]"
    )

    # ── [10] 속성 충족 검증 ──────────────────────────────────────────────────
    attr_result = attr_validator.validate(fields['표준품명'], ev)
    result.속성검증 = attr_validator.format_missing_attrs(attr_result)
    if attr_result['flag']:
        result.플래그_후보.append('FLAG_ATTR_INCOMPLETE')
        logger.info(f"  [10] 속성미충족: {attr_result['missing_attrs']}")

    # ── [11] 제조사 허용 검증 ────────────────────────────────────────────────
    # original_name: simplify_company_name 적용 전 원본값 전달
    original_maker = row.get('제조사', '') or row.get('최초제조사', '')
    maker_result = maker_validator.validate(
        fields['제조사'], original_name=original_maker
    )
    result.제조사검증 = maker_result
    if maker_result['flag']:
        result.플래그_후보.append('FLAG_MAKER_NONSTANDARD')
        logger.info(
            f"  [11] 제조사 비표준: '{fields['제조사'].value}' "
            f"→ 후보: {[c['maker_name'] for c in maker_result['candidates']]}"
        )

    result.표준품명 = fields['표준품명']
    result.표준규격 = fields['표준규격']
    result.제조사   = fields['제조사']
    result.모델명   = fields['모델명']
    result.브랜드   = fields['브랜드']

    # ── [8] 검토 플래그 (기존 + 신규 병합) ───────────────────────────────────
    result.플래그 = flagger.flag(row, ev, fields, policy) + result.플래그_후보

    return result


# =============================================================================
# 메인 실행
# =============================================================================

def main(input_filepath: str):
    logger = setup_logger()
    logger.info('=' * 60)
    logger.info('MDM 표준화 엔진 v1.1 시작')
    logger.info(f'입력 파일: {input_filepath}')

    try:
        df_raw = load_input_file(input_filepath)
        logger.info(f'총 {len(df_raw)}행 로드')
    except Exception as e:
        logger.error(f'파일 로드 실패: {e}')
        sys.exit(1)

    # [1] 정규화
    normalizer = RawInputNormalizer()
    df = normalizer.normalize_dataframe(df_raw)
    logger.info('[1] RawInputNormalizer 완료')

    # 파이프라인 초기화
    ev_collector   = EvidenceCollector()
    policy_router  = StandardizationPolicyRouter()
    fact_finder    = FactFinder(logger=logger)
    field_resolver = StandardFieldResolver()
    flagger        = ReviewFlagger()

    # Standards DB 초기화 (한 번만)
    db_loader       = StandardDBLoader()
    std_matcher     = StandardMatcherStep(db_loader)
    attr_validator  = AttrValidator()
    maker_validator = MakerValidator(db_loader)
    logger.info('[DB] StandardDBLoader 초기화 완료')

    results = []
    total   = len(df)

    for idx, (_, row_series) in enumerate(df.iterrows()):
        row = row_series.to_dict()
        row_num = idx + 1

        logger.info(f'[{row_num}/{total}] 관리번호={row.get("행복나래관리번호", row.get("관리번호", ""))} '
                    f'품명={row.get("품명", "")[:30]}')

        try:
            result = process_row(
                row, ev_collector, policy_router,
                fact_finder, field_resolver, flagger,
                std_matcher, attr_validator, maker_validator,
                logger,
            )
            results.append(result)

            if result.처리가능여부:
                logger.info(
                    f'  → 품명:{result.표준품명.value} | '
                    f'제조사:{result.제조사.value} | '
                    f'모델명:{result.모델명.value} | '
                    f'정책:{result.처리정책} | '
                    f'플래그:{result.플래그}'
                )
            else:
                logger.info(f'  → 처리불가: {result.처리불가사유}')

        except Exception as e:
            logger.error(f'  행 처리 오류: {e}', exc_info=True)
            err_result = StandardResult(
                관리번호     = row.get('행복나래관리번호', row.get('관리번호', '')),
                원본품명     = row.get('품명', ''),
                처리가능여부 = False,
                처리불가사유 = f'처리 오류: {str(e)[:50]}',
            )
            results.append(err_result)

    out_path = save_results(results, OUTPUT_DIR)
    logger.info(f'\n결과 저장 완료: {out_path}')

    total_ok    = sum(1 for r in results if r.처리가능여부)
    total_skip  = sum(1 for r in results if not r.처리가능여부)
    need_review = sum(1 for r in results
                      if r.처리가능여부 and flagger.needs_manual_review(r.플래그))

    logger.info('=' * 60)
    logger.info(f'처리 완료: 총 {total}건')
    logger.info(f'  - 표준화 성공: {total_ok}건')
    logger.info(f'  - 처리불가:   {total_skip}건')
    logger.info(f'  - 수동검토 필요: {need_review}건')
    logger.info('=' * 60)

    return out_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용법: python main.py <입력파일경로>')
        print('예시:  python main.py data/input.xlsx')
        sys.exit(1)

    main(sys.argv[1])