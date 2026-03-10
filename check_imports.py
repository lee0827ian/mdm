import sys
sys.path.insert(0, 'c:/Users/NBC02230024/Desktop/mdm_standardizer')

# policy_router 실제 클래스명 동적 확인
import pipeline.policy_router as pr_mod
print("policy_router exports:", [x for x in dir(pr_mod) if not x.startswith('_')])

import pipeline.evidence_collector as ec_mod
print("evidence_collector exports:", [x for x in dir(ec_mod) if not x.startswith('_')])

import pipeline.normalizer as nm_mod
print("normalizer exports:", [x for x in dir(nm_mod) if not x.startswith('_')])
