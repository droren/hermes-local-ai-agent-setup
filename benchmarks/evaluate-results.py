#!/usr/bin/env python3
"""Automatically score Hermes Next capability benchmark result JSON files."""
from __future__ import annotations

import argparse
import ast
import json
import re
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
    unique = len(set(lines))
    return round(1.0 - (unique / len(lines)), 3)


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
        if k == 'next_action':
            ok = isinstance(got, str) and all(w in got.lower() for w in ['request', 'credentials', 'operations'])
        else:
            ok = got == v
        if ok:
            score += 16
        else:
            reasons.append(f'{k} mismatch: {got!r}')
    return min(score, 100), reasons


def score_summary(text: str) -> tuple[float, list[str]]:
    low = text.lower()
    concepts = ['48 gb', 'local ssd', 'network', 'scheduler']
    hits = sum(1 for c in concepts if c in low)
    score = hits * 20
    lines = [x for x in text.splitlines() if x.strip()]
    if 1 <= len(lines) <= 6:
        score += 20
    reasons = [f'concept hits {hits}/4', f'nonempty lines {len(lines)}']
    return min(score, 100), reasons


def score_review(text: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON']
    score = 20.0 if obj.get('pass') is False else 0.0
    joined = json.dumps(obj).lower()
    if '100' in joined:
        score += 45
    if 'discount' in joined:
        score += 15
    defects = obj.get('defects')
    if isinstance(defects, list) and defects:
        score += 20
    return min(score, 100), ['must identify that 100 percent is valid and should return zero']


def score_test_design(text: str) -> tuple[float, list[str]]:
    obj = extract_json(text)
    if not isinstance(obj, dict):
        return 0.0, ['invalid JSON / wrong format']
    tests = obj.get('tests')
    if not isinstance(tests, list):
        return 10.0, ['missing tests list']
    serialized = json.dumps(tests).lower()
    score = 20.0
    for token in ['-1', '0', '100', '101']:
        if token in serialized:
            score += 15
    if isinstance(obj.get('coverage_note'), str) and obj['coverage_note'].strip():
        score += 20
    return min(score, 100), ['boundary coverage expected: -1, 0, 100, 101']


def score_implement(text: str) -> tuple[float, list[str]]:
    low = text.lower()
    score = 0.0
    if 'def normalize_discount' in low:
        score += 25
    if 'discount < 0' in low:
        score += 20
    if 'discount > 100' in low:
        score += 20
    if 'raise valueerror' in low:
        score += 15
    if 'return discount' in low:
        score += 20
    return min(score, 100), ['expected correct inclusive 0..100 implementation']


SCORERS = {
    'routing.classify': score_routing,
    'structured_output': score_structured,
    'summarization.compact': score_summary,
    'code.review': score_review,
    'test.design': score_test_design,
    'code.implement.small': score_implement,
}


def evaluate(path: Path) -> dict:
    rec = json.loads(path.read_text(encoding='utf-8'))
    capability = rec.get('capability')
    response = rec.get('response', '') or ''
    scorer = SCORERS.get(capability)
    base, reasons = scorer(response) if scorer else (0.0, ['no scorer'])

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='Result JSON files or directories')
    ap.add_argument('--output', default='artifacts/benchmarks/phase1-evaluation.json')
    args = ap.parse_args()

    files = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob('*.json')))
        elif p.is_file():
            files.append(p)
    results = [evaluate(p) for p in files]
    results.sort(key=lambda x: (x.get('model') or '', x.get('capability') or ''))
    payload = {
        'schema_version': 1,
        'scoring_policy': {'pass': '>=80', 'conditional': '60-79.9', 'fail': '<60'},
        'results': results,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for r in results:
        print(f"{r['model']:24} {r['capability']:24} {r['score']:5.1f} {r['grade']}")
    print(out)


if __name__ == '__main__':
    main()
