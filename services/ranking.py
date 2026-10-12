"""Filters and sort orders for the results page."""

SORT_OPTIONS = [
    "Best match",
    "Start here (surveys first)",
    "Most cited",
    "Newest first",
    "Oldest first",
    "Open access first",
]

TYPE_OPTIONS = ["All types", "Surveys / reviews", "Research articles", "Preprints"]


def year_bounds(papers):
    years = [p["year"] for p in papers if p.get("year")]
    return (min(years), max(years)) if years else (None, None)


def apply_filters(papers, year_range=None, oa_only=False, type_choice="All types",
                  min_citations=0, title_contains="", sources=None, has_abstract=False):
    out = []
    kw = (title_contains or "").strip().lower()
    for p in papers:
        if year_range and p.get("year") and not (year_range[0] <= p["year"] <= year_range[1]):
            continue
        if oa_only and not (p.get("is_oa") or p.get("pdf_url")):
            continue
        if type_choice == "Surveys / reviews" and not p.get("is_survey"):
            continue
        if type_choice == "Research articles" and (p.get("type") != "article" or p.get("is_survey")):
            continue
        if type_choice == "Preprints" and p.get("type") != "preprint":
            continue
        if min_citations and (p.get("citations") or 0) < min_citations:
            continue
        if kw and kw not in p["title"].lower():
            continue
        if sources and not set(sources) & set(p.get("sources", [])):
            continue
        if has_abstract and len(p.get("abstract", "")) < 80:
            continue
        out.append(p)
    return out


def sort_papers(papers, how="Best match"):
    def cites(p):
        return p.get("citations") or 0

    if how == "Most cited":
        return sorted(papers, key=lambda p: (cites(p), p["score"]), reverse=True)
    if how == "Newest first":
        return sorted(papers, key=lambda p: (p.get("year") or 0, p["score"]), reverse=True)
    if how == "Oldest first":
        return sorted(papers, key=lambda p: (p.get("year") or 9999, -p["score"]))
    if how == "Open access first":
        return sorted(papers, key=lambda p: (bool(p.get("is_oa") or p.get("pdf_url")), p["score"]), reverse=True)
    if how == "Start here (surveys first)":
        return sorted(papers, key=lambda p: (bool(p.get("is_survey")), p["score"]), reverse=True)
    return sorted(papers, key=lambda p: p["score"], reverse=True)
