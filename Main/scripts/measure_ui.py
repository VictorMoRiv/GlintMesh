"""GlintMesh UI quality measurement (no emojis, ever).

Scores generated agent texts and checks the repo for stray emojis.

Usage:
  python scripts/measure_ui.py --fixtures        # score canned samples in tests/fixtures/ui_samples.json
  python scripts/measure_ui.py <file...>         # score generated texts from files
  python scripts/measure_ui.py --check-repo      # fail if app sources contain emojis
  echo "<text>" | python scripts/measure_ui.py --stdin
"""
import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F]')


def score_interface(text):
    checks = {
        'html_fence': ('```html' in text, 20),
        'doctype_html': ('<!doctype html' in text.lower() and '</html>' in text.lower(), 10),
        'bootstrap_cdn': ('bootstrap' in text.lower(), 15),
        'inline_style': ('<style' in text.lower(), 10),
        'inline_script': ('<script' in text.lower(), 10),
        'no_emoji': (not EMOJI_RE.search(text), 20),
        'disclaimer_or_live': (any(w in text.lower() for w in
            ('sample', 'simulat', 'ejemplo', 'simulad', 'live', 'en vivo', 'tiempo real')), 15),
    }
    return checks


def score_info(text):
    checks = {
        'no_emoji': (not EMOJI_RE.search(text), 50),
        'concise': (len(text) < 2000, 50),
    }
    return checks


def score_text(text):
    category = 'interface' if '```html' in text else 'info'
    checks = score_interface(text) if category == 'interface' else score_info(text)
    score = sum(w for ok, w in checks.values() if ok)
    failed = sorted(name for name, (ok, _) in checks.items() if not ok)
    return {'category': category, 'score': score, 'pass': score >= 80, 'failed': failed}


def check_repo():
    sources = ['main.py', 'mcp_server.py', 'mcp_yahoo.py', 'static/app.js',
               'static/index.html', 'static/sse.mjs', 'scripts/measure_ui.py']
    offenders = {}
    for rel in sources:
        path = BASE / rel
        if not path.exists():
            continue
        found = EMOJI_RE.findall(path.read_text(encoding='utf-8'))
        if found:
            offenders[rel] = sorted(set(found))[:5]
    return offenders


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='*')
    parser.add_argument('--fixtures', action='store_true')
    parser.add_argument('--check-repo', action='store_true')
    parser.add_argument('--stdin', action='store_true')
    args = parser.parse_args()

    ok = True
    if args.check_repo:
        offenders = check_repo()
        print(json.dumps({'repo_emoji_free': not offenders, 'offenders': offenders}, ensure_ascii=False))
        ok = not offenders

    texts = {}
    if args.fixtures:
        samples = json.loads((BASE / 'tests' / 'fixtures' / 'ui_samples.json').read_text(encoding='utf-8'))
        texts.update(samples)
    for path in args.files:
        texts[path] = Path(path).read_text(encoding='utf-8')
    if args.stdin:
        texts['stdin'] = sys.stdin.read()

    for name, text in texts.items():
        result = score_text(text)
        print(json.dumps({'sample': name, **result}, ensure_ascii=False))
        if name.startswith('bad_'):
            if result['pass']:
                print(json.dumps({'error': f'{name} should FAIL but passed'}))
                ok = False
        elif not result['pass']:
            ok = False

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
