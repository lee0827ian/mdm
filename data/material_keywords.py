"""
재질 키워드 사전 (v13.4 계승)
"""

MATERIAL_KEYWORDS = {
    'rubber': [
        'KALREZ', 'VITON', 'NBR', 'EPDM', 'FKM', 'FVMQ', 'HNBR', 'IIR',
        'SBR', 'NR', 'VMQ', 'CR', 'FFKM', 'SILICONE', '실리콘',
        'URETHANE', '우레탄', 'RUBBER', '고무', 'ELASTOMER', '엘라스토머',
        'BUNA', 'NITRILE', 'NEOPRENE', 'FLUOROCARBON', 'PERFLUORO',
    ],
    'plastic': [
        'PTFE', 'TEFLON', 'PVC', 'CPVC', 'PP', 'PE', 'LDPE', 'HDPE',
        'PC', 'ABS', 'POM', 'NYLON', 'PA', 'PU', 'PET', 'PEEK', 'PPE',
        'PS', 'ACRYLIC', '아크릴', 'PLASTIC', '플라스틱', 'RESIN', '수지',
        'FRP', 'GFRP', 'CFRP',
    ],
    'metal': [
        'SUS304', 'SUS316', 'SUS316L', 'SUS', 'STAINLESS', 'STEEL',
        'CARBON STEEL', 'CAST IRON', 'BRASS', '황동',
        'ALUMINUM', 'ALUMINIUM', 'AL', '알루미늄',
        'COPPER', '구리', 'BRONZE', '청동', 'TITANIUM', '티타늄',
        'HSS', 'SKH', 'SKD', 'SCM', 'S45C',
        'A193-B7', 'A194-2H', 'A105', 'A106-B', 'F436',
        'WP304L', 'LOW CARBON',
    ],
    'glass_ceramic': [
        'QUARTZ', '석영', 'BOROSILICATE', 'TEMPERED GLASS',
        'ALUMINA', '알루미나', 'ZIRCONIA', 'CERAMIC', '세라믹',
        'CARBIDE', 'DIAMOND', '다이아몬드',
    ],
    'fiber': [
        'COTTON', '면', 'LEATHER', '가죽', 'NON-WOVEN', '부직포',
        'ARAMID', '아라미드',
    ],
}

# 역방향 인덱스 (빠른 검색용)
MATERIAL_LOOKUP = {}
for _cat, _kws in MATERIAL_KEYWORDS.items():
    for _kw in _kws:
        MATERIAL_LOOKUP[_kw.upper()] = (_cat, _kw)