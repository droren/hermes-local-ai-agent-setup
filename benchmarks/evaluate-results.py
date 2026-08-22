#!/usr/bin/env python3
"""Automatically score Hermes Next capability benchmark result JSON files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def extract_json(text: str):
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find('{')
    end = s.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


def repetition_ratio(text: str) -> float:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if len(lines) < 4:
        return 0.0
    return round(1.0 - (len(set(lines)) / len(lines)), 3)


def score_routing(text: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    reasons = []
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON']
    score = 20.0
    if obj.get('capability') in {'code.implement.small', 'code.implement', 'planning.decomposition'}:
        score += 30; reasons.append('reasonable primary capability')
    if obj.get('complexity') in {'medium', 'large'}:
        score += 20; reasons.append('reasonable complexity')
    if obj.get('needs_decomposition') is True:
        score += 20; reasons.append('correctly requests decomposition')
    if isinstance(obj.get('reason'), str) and obj['reason'].strip():
        score += 10
    return min(score, 100), reasons


def score_structured(text: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON']
    expected = {
        'task_id': 184,
        'status': 'blocked',
        'owner': 'Anna',
        'priority': 'high',
        'next_action': 'request credentials from operations',
    }
    score = 20.0
    reasons = ['valid JSON']
    for k, v in expected.items():
        got = obj.get(k)
        ok = (isinstance(got, str) and all(w in got.lower() for w in ['request', 'credentials', 'operations'])) if k == 'next_action' else got == v
        if ok:
            score += 16
        else:
            reasons.append(f'{k} mismatch: {got!r}')
    return min(score, 100), reasons


def score_summary(text: str) -> tuple[float, list[str]]:
    low = text.lower()
    concepts = ['48 gb', 'local ssd', 'network', 'scheduler']
    hits = sum(1 for c in concepts if c in low)
    lines = [x for x in text.splitlines() if x.strip()]
    score = hits * 20 + (20 if 1 <= len(lines) <= 6 else 0)
    return min(score, 100), [f'concept hits {hits}/4', f'nonempty lines {len(lines)}']


def review_common(text: str, expected_terms: list[str], note: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON']
    joined = json.dumps(obj).lower()
    score = 20.0 if obj.get('pass') is False else 0.0
    hits = sum(1 for term in expected_terms if term.lower() in joined)
    score += 50.0 * (hits / len(expected_terms)) if expected_terms else 0
    defects = obj.get('defects')
    if isinstance(defects, list) and defects:
        score += 20
    missing = obj.get('missing_tests')
    if isinstance(missing, list) and missing:
        score += 10
    return min(score, 100), [note, f'expected-term hits {hits}/{len(expected_terms)}']


def test_design_common(text: str, boundary_tokens: list[str], note: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON / wrong format']
    tests = obj.get('tests')
    if not isinstance(tests, list):
        return 10.0, ['missing tests list']
    serialized = json.dumps(tests).lower()
    score = 20.0
    for token in boundary_tokens:
        if token.lower() in serialized:
            score += 15
    if isinstance(obj.get('coverage_note'), str) and obj['coverage_note'].strip():
        score += 20
    return min(score, 100), [note]


def implement_terms(text: str, required_terms: list[str], note: str) -> tuple[float, list[str]]:
    low = text.lower()
    if not required_terms:
        return 0.0, ['no required terms configured']
    hits = sum(1 for term in required_terms if term.lower() in low)
    return min(100.0, 100.0 * hits / len(required_terms)), [note, f'required-term hits {hits}/{len(required_terms)}']


def fixture_name(rec: dict) -> str:
    return Path(str(rec.get('prompt_file') or '')).name


def score_fixture(rec: dict, response: str) -> tuple[float, list[str]]:
    capability = rec.get('capability')
    fixture = fixture_name(rec)

    if capability == 'routing.classify':
        return score_routing(response)
    if capability == 'structured_output':
        return score_structured(response)
    if capability == 'summarization.compact':
        return score_summary(response)

    if capability == 'code.review':
        if fixture == 'code-review-boundary-2.md':
            return review_common(response, ['1', 'valid'], 'must identify that qty=1 is valid but rejected')
        if fixture == 'code-review-logic-3.md':
            return review_common(response, ['500', 'boundary'], 'must identify that total=500 should qualify')
        return review_common(response, ['100', 'discount'], 'must identify that 100 percent is valid and returns zero')

    if capability == 'test.design':
        if fixture == 'test-design-range-2.md':
            return test_design_common(response, ['17', '18', '120', '121'], 'boundary coverage expected: 17, 18, 120, 121')
        if fixture == 'test-design-branch-3.md':
            return test_design_common(response, ['499', '500', '999', '1000'], 'branch boundaries expected: 499, 500, 999, 1000')
        return test_design_common(response, ['-1', '0', '100', '101'], 'boundary coverage expected: -1, 0, 100, 101')

    if capability == 'code.implement.small':
        if fixture == 'code-implement-range-2.md':
            return implement_terms(response, ['def normalize_age', 'age < 18', 'age > 120', 'raise valueerror', 'return age'], 'expected inclusive 18..120 implementation')
        if fixture == 'code-implement-branch-3.md':
            return implement_terms(response, ['def shipping_band', '500', '1000', 'small', 'free', 'priority'], 'expected three shipping branches')
        return implement_terms(response, ['def normalize_discount', 'discount < 0', 'discount > 100', 'raise valueerror', 'return discount'], 'expected inclusive 0..100 implementation')

    return 0.0, ['no scorer']


def evaluate(path: Path) -> dict:
    rec = json.loads(path.read_text(encoding='utf-8'))
    capability = rec.get('capability')
    response = rec.get('response', '') or ''
    base, reasons = score_fixture(rec, response)

    penalties = []
    if rec.get('status') != 'completed':
        penalties.append(('not_completed', 100))
    if rec.get('done_reason') == 'length':
        penalties.append(('hit_output_limit', 30))
    rr = repetition_ratio(response)
    if rr >= 0.35:
        penalties.append((f'repetition_ratio={rr}', 30))
    wall = float((rec.get('metrics') or {}).get('wall_seconds') or 0)
    if wall > 30:
        penalties.append((f'wall_seconds={wall}', 20))
    if wall > 60:
        penalties.append(('very_slow', 20))

    final = max(0.0, base - sum(p for _, p in penalties))
    grade = 'pass' if final >= 80 else 'conditional' if final >= 60 else 'fail'
    return {
        'file': str(path),
        'fixture': fixture_name(rec),
        'model': rec.get('model'),
        'capability': capability,
        'base_score': round(base, 1),
        'penalties': [{'reason': r, 'points': p} for r, p in penalties],
        'score': round(final, 1),
        'grade': grade,
        'wall_seconds': wall,
        'tokens_per_second': (rec.get('metrics') or {}).get('generation_tokens_per_second'),
        'output_tokens': (rec.get('metrics') or {}).get('output_tokens'),
        'done_reason': rec.get('done_reason'),
        'repetition_ratio': rr,
        'reasons': reasons,
    }


def default_output(paths: list[str]) -> Path:
    if len(paths) == 1:
        p = Path(paths[0])
        if p.is_dir():
            return p.parent / f'{p.name}-evaluation.json'
        if p.is_file():
            return p.with_name(f'{p.stem}-evaluation.json')
    return Path('artifacts/benchmarks/evaluation.json')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='Result JSON files or directories')
    ap.add_argument('--output', help='Explicit evaluation JSON path')
    args = ap.parse_args()

    files = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob('*.json')))
        elif p.is_file():
            files.append(p)
    results = [evaluate(p) for p in files]
    results.sort(key=lambda x: (x.get('model') or '', x.get('capability') or '', x.get('fixture') or ''))
    payload = {
        'schema_version': 3,
        'scoring_policy': {'pass': '>=80', 'conditional': '60-79.9', 'fail': '<60'},
        'results': results,
    }
    out = Path(args.output) if args.output else default_output(args.paths)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for r in results:
        print(f"{r['model']:24} {r['capability']:24} {r['score']:5.1f} {r['grade']:11} {r['fixture']}")
    print(out)


if __name__ == '__main__':
    main()
