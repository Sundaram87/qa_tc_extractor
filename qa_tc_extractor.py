#!/usr/bin/env python3
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Set


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}
SUPPORTED_SOURCES = ("files", "emails", "meetings", "teams")
LEVEL_0_LABELS = {"0", "l0", "level0", "level_0"}


def tokenize(*values: object) -> Set[str]:
    tokens: Set[str] = set()
    for value in values:
        if value is None:
            continue
        for token in re.findall(r"[A-Za-z0-9_]+", str(value).lower()):
            if token not in STOP_WORDS and len(token) > 2:
                tokens.add(token)
    return tokens


def sorted_unique(values: Iterable[str]) -> List[str]:
    return sorted({value for value in values if value})


@dataclass(frozen=True)
class Evidence:
    source_type: str
    title: str
    content: str

    @property
    def haystack(self) -> str:
        return f"{self.title}\n{self.content}".lower()


@dataclass(frozen=True)
class ChangeRequest:
    cr_id: str
    title: str
    component: str = ""
    description: str = ""
    release_notes: str = ""
    references: Sequence[str] = field(default_factory=tuple)

    @property
    def keywords(self) -> Set[str]:
        return tokenize(
            self.cr_id,
            self.title,
            self.component,
            self.description,
            self.release_notes,
            *self.references,
        )


@dataclass(frozen=True)
class TestCase:
    test_id: str
    title: str
    level: str
    area: str = ""
    steps: str = ""
    keywords: Sequence[str] = field(default_factory=tuple)

    @property
    def is_level_0(self) -> bool:
        normalized = str(self.level).strip().lower().replace(" ", "").replace("-", "").replace("_", "")
        return normalized in LEVEL_0_LABELS

    @property
    def terms(self) -> Set[str]:
        return tokenize(self.test_id, self.title, self.area, self.steps, *self.keywords)


def load_change_requests(payload: Dict[str, object]) -> List[ChangeRequest]:
    result = []
    for item in payload.get("change_requests", []):
        result.append(
            ChangeRequest(
                cr_id=str(item.get("id", "")).strip(),
                title=str(item.get("title", "")).strip(),
                component=str(item.get("component", "")).strip(),
                description=str(item.get("description", "")).strip(),
                release_notes=str(item.get("release_notes", "")).strip(),
                references=tuple(item.get("references", []) or []),
            )
        )
    return result


def load_evidence(payload: Dict[str, object]) -> List[Evidence]:
    result = []
    for item in payload.get("release_evidence", []):
        result.append(
            Evidence(
                source_type=str(item.get("source_type", "")).strip().lower(),
                title=str(item.get("title", "")).strip(),
                content=str(item.get("content", "")).strip(),
            )
        )
    return result


def load_test_cases(payload: Dict[str, object]) -> List[TestCase]:
    result = []
    for item in payload.get("level0_test_cases", []):
        result.append(
            TestCase(
                test_id=str(item.get("id", "")).strip(),
                title=str(item.get("title", "")).strip(),
                level=str(item.get("level", "")).strip(),
                area=str(item.get("area", "")).strip(),
                steps=str(item.get("steps", "")).strip(),
                keywords=tuple(item.get("keywords", []) or []),
            )
        )
    return result


def evidence_matches(cr: ChangeRequest, evidence: Evidence) -> Set[str]:
    return {token for token in cr.keywords if token in evidence.haystack}


def test_matches(cr: ChangeRequest, test_case: TestCase, evidence: Sequence[Evidence]) -> Dict[str, object]:
    test_terms = test_case.terms
    cr_overlap = test_terms & cr.keywords
    matched_sources = set()
    matched_tokens = set()
    supporting_titles = []

    for item in evidence:
        overlap = test_terms & evidence_matches(cr, item)
        if overlap:
            matched_sources.add(item.source_type)
            matched_tokens.update(overlap)
            if item.title:
                supporting_titles.append(item.title)

    source_count = len(matched_sources)
    token_count = len(matched_tokens)

    if source_count >= 2 and token_count >= 2:
        coverage_fit = "strong"
        confidence = "high"
    elif source_count >= 1 and token_count >= 2:
        coverage_fit = "partial"
        confidence = "medium"
    else:
        coverage_fit = "gap"
        confidence = "low"

    evidence_gaps = []
    if not matched_sources:
        evidence_gaps.append("No corroborating release evidence linked this Level 0 test case to the CR.")
    missing_sources = [source for source in SUPPORTED_SOURCES if source not in matched_sources]
    if matched_sources and missing_sources:
        evidence_gaps.append(f"Missing corroboration from: {', '.join(missing_sources)}.")

    rationale = []
    if cr_overlap:
        rationale.append(f"Keyword overlap with CR: {', '.join(sorted(cr_overlap))}.")
    if supporting_titles:
        rationale.append(f"Supporting evidence: {', '.join(sorted_unique(supporting_titles)[:3])}.")
    if not rationale:
        rationale.append("Coverage is inferred from limited metadata only.")

    return {
        "test_id": test_case.test_id,
        "title": test_case.title,
        "area": test_case.area,
        "coverage_fit": coverage_fit,
        "confidence": confidence,
        "matched_sources": sorted(matched_sources),
        "matched_keywords": sorted(matched_tokens),
        "rationale": " ".join(rationale),
        "evidence_gaps": evidence_gaps,
        "score": (source_count * 10) + token_count if matched_sources else 0,
        "cr_overlap": sorted(cr_overlap),
    }


def analyze(payload: Dict[str, object]) -> Dict[str, object]:
    change_requests = load_change_requests(payload)
    evidence = load_evidence(payload)
    test_cases = [test_case for test_case in load_test_cases(payload) if test_case.is_level_0]

    confirmed_facts = []
    hypotheses = []
    impacted = []

    available_sources = {item.source_type for item in evidence if item.source_type}
    repository_gaps = [source for source in SUPPORTED_SOURCES if source not in available_sources]

    for cr in sorted(change_requests, key=lambda item: item.cr_id or item.title):
        matched_evidence = []
        matched_tokens = set()
        for item in evidence:
            overlap = evidence_matches(cr, item)
            if overlap:
                matched_evidence.append(item)
                matched_tokens.update(overlap)
                confirmed_facts.append(
                    f"{cr.cr_id or cr.title} is referenced in {item.source_type}: {item.title or item.content[:60]}"
                )

        if not matched_evidence:
            hypotheses.append(
                f"{cr.cr_id or cr.title} lacks explicit supporting evidence across files, emails, meetings, or Teams."
            )

        cr_results = []
        for test_case in test_cases:
            result = test_matches(cr, test_case, matched_evidence)
            if result["score"] > 0:
                cr_results.append(result)
            elif result["cr_overlap"]:
                hypotheses.append(
                    f"{test_case.test_id} may be relevant to {cr.cr_id or cr.title}, but release evidence is missing."
                )

        cr_results.sort(key=lambda item: (-item["score"], item["test_id"], item["title"]))
        impacted.append(
            {
                "change_request": {
                    "id": cr.cr_id,
                    "title": cr.title,
                    "component": cr.component,
                },
                "confidence": "high" if len(matched_evidence) >= 2 else "medium" if matched_evidence else "low",
                "confirmed_evidence_count": len(matched_evidence),
                "matched_keywords": sorted(matched_tokens),
                "impacted_level0_tests": [
                    {key: value for key, value in item.items() if key not in {"score", "cr_overlap"}}
                    for item in cr_results
                ],
                "evidence_gaps": (
                    [f"No evidence found in: {', '.join(repository_gaps)}."] if repository_gaps else []
                ),
            }
        )

    overall_gaps = []
    if not evidence:
        overall_gaps.append("No release evidence was provided.")
    if repository_gaps:
        overall_gaps.append(f"Search coverage missing source types: {', '.join(repository_gaps)}.")
    if not test_cases:
        overall_gaps.append("No Level 0 regression test cases were provided.")

    proposal_lines = []
    for item in impacted:
        tests = item["impacted_level0_tests"]
        if tests:
            top_tests = ", ".join(test["test_id"] for test in tests[:3])
            proposal_lines.append(
                f"{item['change_request']['id'] or item['change_request']['title']}: run {top_tests} for QA sign-off."
            )
        else:
            proposal_lines.append(
                f"{item['change_request']['id'] or item['change_request']['title']}: no confirmed Level 0 coverage; manual QA triage required."
            )

    email_summary = {
        "subject": "QA Level 0 regression proposal",
        "body": " ".join(proposal_lines) if proposal_lines else "No impacted Level 0 regression tests were identified.",
    }

    return {
        "search_scope": list(SUPPORTED_SOURCES),
        "confirmed_facts": sorted_unique(confirmed_facts),
        "hypotheses": sorted_unique(hypotheses),
        "impacted_change_requests": impacted,
        "overall_evidence_gaps": overall_gaps,
        "qa_sign_off_proposal": proposal_lines,
        "email_handoff": email_summary,
    }


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print("Usage: qa_tc_extractor.py <input.json>", file=sys.stderr)
        return 1

    with open(argv[1], "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    print(json.dumps(analyze(payload), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
