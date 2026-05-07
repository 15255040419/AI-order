import re


def normalize_key(value):
    """
    Normalize only harmless presentation differences.

    Matching is still exact after this normalization. There is no alias,
    contains, or fuzzy matching.
    """
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text.upper()


def strip_qty_suffix(value):
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s*[*xX×]\s*\d+\s*$", "", text)
    text = re.sub(r"\s+\d+\s*(台|个|卷|套|箱|包|张|件)\s*$", "", text)
    return text.strip()


def product_identity(info, match_type=""):
    if str(match_type).startswith("exact:stock"):
        stock_identity = str(info.get("规格编号") or "").strip()
        if stock_identity:
            return stock_identity
    return str(info.get("货品名称") or "").strip()


def _query_keys(query):
    raw_query = str(query or "").strip()
    cleaned_query = strip_qty_suffix(raw_query)
    keys = {normalize_key(raw_query), normalize_key(cleaned_query)}
    keys.discard("")
    return keys


def _iter_frame_rows(frame):
    if frame is None or getattr(frame, "empty", True):
        return
    for _, row in frame.iterrows():
        yield row.to_dict()


def _unique_result(matches, match_type):
    unique = []
    seen = set()
    for info in matches:
        row_key = (
            str(info.get("货品名称", "")),
            str(info.get("规格编号", "")),
            str(info.get("货品编号", "")),
            str(info.get("条码", "")),
            str(info.get("货品条码", "")),
            str(info.get("规格", "")),
        )
        if row_key not in seen:
            unique.append(info)
            seen.add(row_key)

    if len(unique) == 1:
        return {
            "matched": product_identity(unique[0], match_type),
            "details": unique[0],
            "status": "matched",
            "matchType": match_type,
            "candidates": [],
        }

    if len(unique) > 1:
        return {
            "matched": None,
            "details": {},
            "status": "ambiguous",
            "matchType": f"{match_type}:multiple",
            "candidates": [product_identity(info, match_type) for info in unique if product_identity(info, match_type)],
        }

    return None


def find_strict_match(query, data_loader):
    """
    Product resolver using the user's exact table rules:

    - Cashier machines / integrated scales: match only
      `总库存-组合装明细.xlsx` column `货品名称`.
    - Other goods: match only `总库存.xlsx` column `规格编号`.

    No product aliases, no product-name matching in 总库存.xlsx, no contains
    matching, and no fuzzy matching.
    """
    keys = _query_keys(query)
    if not keys or not data_loader:
        return {
            "matched": None,
            "details": {},
            "status": "unmatched",
            "matchType": "empty",
            "candidates": [],
        }

    combo_index = getattr(data_loader, "normalized_combo_name_index", None) or {}
    combo_matches = []
    if combo_index:
        for key in keys:
            combo_matches.extend(combo_index.get(key, []))
    else:
        for info in _iter_frame_rows(getattr(data_loader, "combo_data", None)):
            if normalize_key(info.get("货品名称")) in keys:
                combo_matches.append(info)

    combo_result = _unique_result(combo_matches, "exact:combo.货品名称")
    if combo_result:
        return combo_result

    item_index = getattr(data_loader, "normalized_item_no_index", None) or {}
    stock_matches = []
    if item_index:
        for key in keys:
            stock_matches.extend(item_index.get(key, []))
    else:
        for info in _iter_frame_rows(getattr(data_loader, "stock_data", None)):
            if normalize_key(info.get("规格编号")) in keys:
                stock_matches.append(info)

    stock_result = _unique_result(stock_matches, "exact:stock.规格编号")
    if stock_result:
        return stock_result

    return {
        "matched": None,
        "details": {},
        "status": "unmatched",
        "matchType": "no_exact_combo_name_or_stock_spec_no",
        "candidates": [],
    }


def find_best_match(query, choices, data_loader=None, threshold=0.1):
    result = find_strict_match(query, data_loader)
    return result["matched"]


def get_product_details(matched_name, data_loader):
    if not matched_name or not data_loader:
        return {}

    target = normalize_key(matched_name)
    for info in _iter_frame_rows(getattr(data_loader, "combo_data", None)):
        if normalize_key(info.get("货品名称")) == target:
            return info
    for info in _iter_frame_rows(getattr(data_loader, "stock_data", None)):
        if normalize_key(info.get("货品名称")) == target:
            return info
    return {}
