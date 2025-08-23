import os, re, json, sys, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

CODE_DIRS = ["src", "tests"]
COMMENT_RE = re.compile(r"^\s*#")

def classify_file(path: str) -> str:
    if path.startswith('src'):
        return 'src'
    if path.startswith('tests'):
        return 'tests'
    return 'other'

def collect():
    metrics = []
    for base in CODE_DIRS:
        base_path = os.path.join(ROOT, base)
        if not os.path.isdir(base_path):
            continue
        for dirpath, _, filenames in os.walk(base_path):
            if '__pycache__' in dirpath:
                continue
            for fn in filenames:
                if fn.endswith('.py'):
                    fp = os.path.join(dirpath, fn)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as fh:
                            lines = fh.readlines()
                    except Exception:
                        continue
                    total = len(lines)
                    blank = sum(1 for l in lines if l.strip() == '')
                    comment = sum(1 for l in lines if COMMENT_RE.match(l))
                    code = total - blank - comment
                    rel = os.path.relpath(fp, ROOT).replace('\\', '/')
                    metrics.append({
                        'file': rel,
                        'group': classify_file(rel),
                        'total': total,
                        'code': code,
                        'blank': blank,
                        'comment': comment
                    })
    return metrics

def aggregate(metrics):
    agg = {
        'files': len(metrics),
        'total_lines': sum(m['total'] for m in metrics),
        'code_lines': sum(m['code'] for m in metrics),
        'blank_lines': sum(m['blank'] for m in metrics),
        'comment_lines': sum(m['comment'] for m in metrics),
    }
    for group in ('src', 'tests'):
        gcode = sum(m['code'] for m in metrics if m['group'] == group)
        agg[f'{group}_code_lines'] = gcode
    src_code = agg.get('src_code_lines', 0) or 1
    agg['test_to_src_code_ratio_pct'] = round(100 * agg.get('tests_code_lines', 0) / src_code, 2)
    return agg

def to_markdown(metrics, agg):
    lines = []
    lines.append(f"Generated: {datetime.datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("Overall Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for k, v in agg.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("Per File (top 30 by code lines)")
    lines.append("")
    lines.append("| File | Code | Total | Blank | Comment |")
    lines.append("|------|------|-------|-------|---------|")
    for m in sorted(metrics, key=lambda x: x['code'], reverse=True)[:30]:
        lines.append(f"| {m['file']} | {m['code']} | {m['total']} | {m['blank']} | {m['comment']} |")
    return "\n".join(lines)

def main():
    metrics = collect()
    agg = aggregate(metrics)
    if '--json' in sys.argv:
        print(json.dumps({'aggregate': agg, 'files': metrics}, indent=2))
    else:
        print(to_markdown(metrics, agg))

if __name__ == '__main__':
    main()