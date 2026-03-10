import sys
sys.path.insert(0, 'c:/Users/NBC02230024/Desktop/mdm_standardizer')

from pipeline.normalizer import RawInputNormalizer
from pipeline.evidence_collector import EvidenceCollector
from pipeline.policy_router import StandardizationPolicyRouter

normalizer    = RawInputNormalizer()
ev_collector  = EvidenceCollector()
policy_router = StandardizationPolicyRouter()

cases = [
    {
        "행복나래관리번호": "28720872",
        "품명": "AB 슬라이드 리바운드",
        "규격": "16.5cm x 40cm , 1275g , 24,900원",
        "제조사": "제로투히어로",
        "모델명": "AB Slide Rebound",
        "표준구분": "표준구분",
        "고객개별주문사유": "URL정보 : https://brand.naver.com/zerotohero/products/11751180077",
        "행복나래메모": "",
        "비고": "정상",
    },
    {
        "행복나래관리번호": "28720892",
        "품명": "ES-1100 스트라이크 PS락",
        "규격": "DC12V / DC24V 사용 패닉바락",
        "제조사": "",
        "모델명": "",
        "표준구분": "표준구분",
        "고객개별주문사유": "https://smartstore.naver.com/idgate/products/5359543334",
        "행복나래메모": "",
        "비고": "정상",
    },
]

for row in cases:
    print("="*60)
    print("품명:", row["품명"])
    norm_row        = normalizer.normalize_row(row)
    ev              = ev_collector.collect(norm_row)
    policy, skip, _ = policy_router.route(norm_row, ev)
    print("policy:", policy, "skip:", skip)
    print("name_candidates:")
    for v, s in ev.name_candidates:
        print(f"  {s:20}: {repr(v)}")
