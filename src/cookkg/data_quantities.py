"""Conservative, source-bound quantity and preparation observations.

Numbers are never aggregated across sections: 1 egg and about 60 g describe the
same item, and separate sections can contradict each other. Ambiguous context
is retained explicitly instead of assigning a guessed amount to an ingredient.
"""

import re

from cookkg.data_models import Evidence, Preparation, Quantity

NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
UNIT = (r"(?:千克|公斤|毫升|小块|小勺|大勺|茶匙|汤匙|kg|ml|mL|ML|Kg|KG|"
        r"克|斤|两|升|个|颗|根|片|瓣|块|勺|滴|枚|袋|盒|罐|杯|碗|只|粒|把|包|条|扎|圈|份|g|G|L|l)")
AMOUNT = re.compile(
    rf"(?<![\d./])(?P<approx>约|大约)?\s*(?P<a>{NUMBER})\s*"
    rf"(?:(?P<op>[-—~～至到±])\s*(?P<b>{NUMBER})\s*)?(?P<unit>{UNIT})"
)
ADJUSTMENT = re.compile(
    rf"(?P<a>{NUMBER})\s*(?P<unit>{UNIT})\s*(?:[（(][^±\n]*)?±\s*(?P<b>{NUMBER})\s*(?P<unit2>{UNIT})"
)
REPEATED_UNIT_RANGE = re.compile(
    rf"(?P<a>{NUMBER})\s*(?P<unit>{UNIT})\s*[-—~～至到]\s*"
    rf"(?P<b>{NUMBER})\s*(?P<unit2>{UNIT})"
)
QUALITATIVE = re.compile(r"适量|少许|若干|少量")
FORM = re.compile(r"切成[片丝丁块末段]|切[片丝丁块末段]|切碎|剁碎|打散|冷冻|去皮|去骨|去籽")


def mentioned(text: str, names: dict[str, list[str]]) -> set[str]:
    """Prefer the longest surface: 葱 in 洋葱 and 油 in 蚝油 are not extra entities."""
    spans = [(m.start(), m.end(), key) for key, variants in names.items()
             for name in variants if name for m in re.finditer(re.escape(name), text)]
    return {key for start, end, key in spans if not any(
        other_start <= start and end <= other_end and other_end - other_start > end - start
        for other_start, other_end, _ in spans)}


def observe_quantities(line: str, evidence_line: int, names: list[str],
                       all_names: dict[str, list[str]], ingredient_id: str) -> list[dict]:
    """Extract only local ingredient clauses, or explicit combined totals."""
    evidence = Evidence(line=evidence_line, text=line)
    # Only split true clause separators; never split a decimal point or Chinese
    # enumeration comma, which can bind several ingredients to one total.
    clauses = re.split(r"[，,；;。]", line)
    mentions = mentioned(line, all_names)
    combined = bool(re.search(r"共|合计|总量|总重", line)) and len(mentions) > 1
    if combined:
        candidates = [(line, "combined", sorted(mentions))]
    else:
        candidates = [(c, "ingredient", []) for c in clauses
                      if ingredient_id in mentioned(c, all_names)]
        # A single-ingredient ingredient-list row can put its amount after a comma.
        if mentions == {ingredient_id} and re.match(r"\s*[-*]\s*", line):
            candidates = [(line, "ingredient", [])]
    results = []
    for clause, scope, members in candidates:
        local_mentions = mentioned(clause, all_names)
        if scope != "combined" and len(local_mentions - {ingredient_id}) > 0:
            # Multiple independent amounts in one clause need manual assignment.
            continue
        common = dict(scope=scope, member_ids=members, evidence=evidence)
        # Keep formulas/per-item ratios unevaluated, including Chinese multiplier wording.
        content = re.sub(r"^\s*[-*]\s*", "", clause)
        if re.search(r"元|推荐长宽高|整包", clause):
            continue
        if re.search(r"(?<!\*)\*(?!\*)|×|/|每|份数|倍|分之", content):
            if (AMOUNT.search(clause) or re.search(rf"{NUMBER}/{NUMBER}\s*{UNIT}", clause)
                    or re.search(r"倍|分之|张数", clause)):
                results.append(Quantity(kind="formula", raw=clause.strip(),
                                        formula=clause.strip(), **common))
            continue
        ranges = list(REPEATED_UNIT_RANGE.finditer(clause))
        for match in ranges:
            if match["unit"] == match["unit2"] and float(match["a"]) <= float(match["b"]):
                results.append(Quantity(kind="range", raw=match[0], unit=match["unit"],
                    minimum=float(match["a"]), maximum=float(match["b"]), **common))
        adjustments = list(ADJUSTMENT.finditer(clause))
        for match in adjustments:
            if match["unit"] == match["unit2"]:
                results.append(Quantity(kind="adjustable", raw=match[0],
                    value=float(match["a"]), adjustment=float(match["b"]),
                    unit=match["unit"], **common))
        for match in AMOUNT.finditer(clause):
            if any(a.start() < match.end() and match.start() < a.end()
                   for a in [*adjustments, *ranges]):
                continue
            # Reject recipe fractions (1/2), degrees and adjustment-only expressions.
            if match.start() and clause[match.start() - 1] in "/±":
                continue
            a = float(match["a"])
            b = float(match["b"]) if match["b"] else None
            attrs = dict(raw=match[0].strip(), unit=match["unit"],
                         approximate=bool(match["approx"]), **common)
            if match["op"] == "±":
                results.append(Quantity(kind="adjustable", value=a, adjustment=b, **attrs))
            elif match["op"]:
                if a <= b:
                    results.append(Quantity(kind="range", minimum=a, maximum=b, **attrs))
            else:
                # "最多/至少/以内" is a bound, not an exact amount.
                around = clause[max(0, match.start() - 4):match.end() + 4]
                if re.search(r"至少|最多|以内|以上|以下|不超过", around):
                    continue
                results.append(Quantity(kind="exact", value=a, **attrs))
        for match in QUALITATIVE.finditer(clause):
            results.append(Quantity(kind="qualitative", raw=match[0], **common))
    if not results:
        results = [Quantity(kind="unparsed", scope="context", raw=line, evidence=evidence)]
    return [r.model_dump(mode="json") for r in results]


def observe_forms(evidence: list[dict], names: list[str],
                  all_names: dict[str, list[str]], ingredient_id: str) -> list[dict]:
    results = []
    seen = set()
    for item in evidence:
        for clause in re.split(r"[，,；;。]", item["text"]):
            if not any(n in clause for n in names):
                continue
            others = mentioned(clause, all_names) - {ingredient_id}
            if others or re.search(r"不[要需用]?切|无需|不用|不要", clause):
                continue
            values = [m[0] for m in FORM.finditer(clause)]
            # Preserve explicitly attached forms such as 蒜末/姜片/葱花.
            for name in names:
                for suffix in ("薄片", "末", "片", "丝", "丁", "段", "花", "液", "条"):
                    if name + suffix in clause:
                        values.append(suffix)
            for value in values:
                key = (value, item["line"])
                if key not in seen:
                    results.append(Preparation(form=value, evidence=item).model_dump(mode="json"))
                    seen.add(key)
    return results


def enrich_annotation(annotation: dict, aliases: list[dict] | None = None,
                      text: str | None = None) -> dict:
    """Return explicit observations for review; source annotation remains AI-assisted."""
    import copy

    result = copy.deepcopy(annotation)
    names = {u["id"]: list(dict.fromkeys([u["surface"], u["id"]]))
             for u in result["ingredients"]}
    for alias in aliases or []:
        if alias["scope"] == annotation["id"] and alias["canonical"] in names:
            names[alias["canonical"]].append(alias["alias"])
    for use in result["ingredients"]:
        if text is not None:
            section = ""
            evidence_seen = {e["line"] for e in use["evidence"]}
            for n, line in enumerate(text.splitlines(), 1):
                if line.startswith("## "):
                    section = line[3:]
                if use["id"] not in mentioned(line, names):
                    continue
                is_quantity = (any(s in section for s in ("计算", "必备原料"))
                               and re.match(r"\s*[-*]\s+", line)
                               and (AMOUNT.search(line) or QUALITATIVE.search(line))
                               and any(q["scope"] != "context" for q in observe_quantities(
                                   line, n, names[use["id"]], names, use["id"])))
                has_form = ("操作" in section and observe_forms(
                    [dict(line=n, text=line)], names[use["id"]], names, use["id"]))
                if is_quantity or has_form:
                    if n not in evidence_seen:
                        use["evidence"].append(dict(line=n, text=line))
                        evidence_seen.add(n)
                    if is_quantity and line not in use["quantity_raw"]:
                        use["quantity_raw"].append(line)
            use["evidence"].sort(key=lambda e: e["line"])
        use["quantities"] = []
        use["quantity_raw"] = list(dict.fromkeys(use["quantity_raw"]))
        for e in use["evidence"]:
            if e["text"] not in use["quantity_raw"]:
                continue
            use["quantities"].extend(observe_quantities(
                e["text"], e["line"], names[use["id"]], names, use["id"]))
        use["forms"] = observe_forms(use["evidence"], names[use["id"]], names, use["id"])
    return result
