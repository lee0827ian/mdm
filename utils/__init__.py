from utils.text_utils import (
    is_placeholder, clean_value, normalize_text,
    fix_numeric_model, remove_noise_patterns,
    extract_bracket_content, split_key_value,
    normalize_model_name, simplify_company_name,
    tokenize_korean,
)
from utils.domain_utils import (
    extract_domain, get_store_hint,
    is_blocked_domain, is_marketplace,
)
from utils.safe_crawler import SafeCrawler