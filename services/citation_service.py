"""Reference formatting: APA 7, IEEE, MLA 9, BibTeX and RIS."""
import re

STYLES = ["APA", "IEEE", "MLA", "BibTeX", "RIS"]


def _split_name(name):
    """Return (surname, [initials])."""
    name = " ".join(str(name).split())
    if not name:
        return "", []
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
    else:
        parts = name.split(" ")
        if len(parts) == 1:
            return parts[0], []
        if re.fullmatch(r"[A-Z]{1,3}", parts[-1]) and not name.isupper():   # "Smith JA" (Europe PMC)
            return " ".join(parts[:-1]), list(parts[-1])
        last, first = parts[-1], " ".join(parts[:-1])
    if first.isupper() and len(first) <= 3 and " " not in first:
        return last, list(first)
    return last, [w[0].upper() for w in re.split(r"[\s\-.]+", first) if w]


def _apa_author(name):
    last, ini = _split_name(name)
    return f"{last}, {' '.join(i + '.' for i in ini)}".strip(", ") if ini else last


def _ieee_author(name):
    last, ini = _split_name(name)
    return f"{' '.join(i + '.' for i in ini)} {last}".strip()


def _join_and(items):
    """APA 7 style list: 'A, & B' and 'A, B, & C'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + ", & " + items[-1]


def _doi_url(p):
    return f"https://doi.org/{p['doi']}" if p.get("doi") else (p.get("url") or "")


def _year(p):
    return str(p["year"]) if p.get("year") else "n.d."


def _end(text):
    return text if text.endswith((".", "?", "!")) else text + "."


def apa(p):
    names = [_apa_author(a) for a in p.get("authors", [])]
    if len(names) > 20:
        names = names[:19] + ["..."] + [names[-1]]
    authors = _join_and(names) if names else ""
    lead = f"{authors} ({_year(p)})." if authors else f"({_year(p)})."
    parts = [lead, _end(p["title"])]
    if p.get("venue"):
        parts.append(_end(p["venue"]))
    link = _doi_url(p)
    if link:
        parts.append(link)
    return " ".join(parts)


def ieee(p):
    names = [_ieee_author(a) for a in p.get("authors", [])]
    if len(names) > 6:
        authors = names[0] + " et al."
    elif len(names) > 2:
        authors = ", ".join(names[:-1]) + ", and " + names[-1]
    else:
        authors = " and ".join(names)
    text = (authors + ", " if authors else "") + f"“{p['title']},”"
    if p.get("venue"):
        text += f" {p['venue']},"
    text += f" {p['year']}." if p.get("year") else ""
    if p.get("doi"):
        text += f" doi: {p['doi']}."
    elif p.get("url"):
        text += f" [Online]. Available: {p['url']}"
    return text.replace(",.", ".").strip()


def mla(p):
    people = []
    for i, a in enumerate(p.get("authors", [])):
        last, ini = _split_name(a)
        first = " ".join(i2 + "." for i2 in ini)
        people.append(f"{last}, {first}".strip(", ") if i == 0 else f"{first} {last}".strip())
    if len(people) > 2:
        authors = people[0] + ", et al."
    elif len(people) == 2:
        authors = f"{people[0]}, and {people[1]}."
    else:
        authors = _end(people[0]) if people else ""
    parts = [authors] if authors else []
    parts.append(f"“{_end(p['title'])}”")
    tail = ", ".join(x for x in (p.get("venue"), str(p["year"]) if p.get("year") else "", _doi_url(p)) if x)
    if tail:
        parts.append(_end(tail))
    return " ".join(parts)


def _bib_escape(text):
    return re.sub(r"([&%$#_])", r"\\\1", str(text or "")).replace("{", "\\{").replace("}", "\\}")


def bibtex(p):
    last = _split_name(p["authors"][0])[0] if p.get("authors") else "anon"
    word = re.sub(r"[^a-z0-9]", "", (p["title"].split() or ["paper"])[0].lower())
    key = re.sub(r"[^A-Za-z0-9]", "", last) + (str(p["year"]) if p.get("year") else "nd") + word
    preprint = p.get("type") == "preprint" or (p.get("venue") or "").lower().startswith("arxiv")
    etype = "misc" if preprint or not p.get("venue") else "article"
    fields = [("title", "{" + _bib_escape(p["title"]) + "}"),
              ("author", " and ".join(p.get("authors", [])))]
    if p.get("year"):
        fields.append(("year", str(p["year"])))
    if p.get("venue") and etype == "article":
        fields.append(("journal", _bib_escape(p["venue"])))
    if p.get("doi"):
        fields.append(("doi", p["doi"]))
    if p.get("url"):
        fields.append(("url", p["url"]))
    if p.get("arxiv_id"):
        fields += [("eprint", p["arxiv_id"]), ("archivePrefix", "arXiv")]
    lines = []
    for k, v in fields:
        if not v:
            continue
        if k == "author":
            v = _bib_escape(v)
        lines.append(f"  {k} = {v}" if k == "title" else f"  {k} = {{{v}}}")
    return f"@{etype}{{{key},\n" + ",\n".join(lines) + "\n}"


def ris(p):
    preprint = p.get("type") == "preprint"
    lines = [f"TY  - {'GEN' if preprint else 'JOUR'}"]
    for a in p.get("authors", []):
        last, ini = _split_name(a)
        lines.append(f"AU  - {last}, {' '.join(i + '.' for i in ini)}".rstrip(", "))
    lines.append(f"TI  - {p['title']}")
    if p.get("venue"):
        lines.append(f"JO  - {p['venue']}")
    if p.get("year"):
        lines.append(f"PY  - {p['year']}")
    if p.get("doi"):
        lines.append(f"DO  - {p['doi']}")
    if p.get("url"):
        lines.append(f"UR  - {p['url']}")
    if p.get("abstract"):
        lines.append(f"AB  - {p['abstract']}")
    lines.append("ER  - ")
    return "\n".join(lines)


_FORMATTERS = {"APA": apa, "IEEE": ieee, "MLA": mla, "BibTeX": bibtex, "RIS": ris}


def format_citation(paper, style="APA"):
    return _FORMATTERS[style](paper)


def format_many(papers, style="APA"):
    if style in ("APA", "MLA"):
        papers = sorted(papers, key=lambda p: (p.get("authors") or [p["title"]])[0].lower())
    if style == "IEEE":
        return "\n".join(f"[{i}] {ieee(p)}" for i, p in enumerate(papers, 1))
    return "\n\n".join(format_citation(p, style) for p in papers)


def file_extension(style):
    return {"BibTeX": "bib", "RIS": "ris"}.get(style, "txt")
