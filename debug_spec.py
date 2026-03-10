import sys
sys.path.insert(0, 'c:/Users/NBC02230024/Desktop/mdm_standardizer')

import pandas as pd
from pipeline.normalizer import RawInputNormalizer
from pipeline.evidence_collector import EvidenceCollector

normalizer   = RawInputNormalizer()
ev_collector = EvidenceCollector()

df_raw = pd.DataFrame([{
    "행복나래관리번호": "28721242",
    "품명": "충전햄머드릴",
    "규격": "밀워키 M18 FPD2-0X 충전햄머드릴 본체 젠3 손잡이포함 BL모터",
    "제조사": "",
    "모델명": "",
    "표준구분": "표준구분",
    "고객개별주문사유": "",
    "행복나래메모": "",
    "비고": "정상",
}])

df  = normalizer.normalize_dataframe(df_raw)
row = df.iloc[0].to_dict()
ev  = ev_collector.collect(row)

print("inline_maker :", ev.parsed_spec.get("inline_maker"))
print("inline_model :", ev.parsed_spec.get("inline_model"))
print("maker_candidates:", ev.maker_candidates)
print("model_candidates:", ev.model_candidates)
