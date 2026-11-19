"""Read-only FIEBDC-3 (BC3) parser for Stage 4.0B inspection tables.

Usage: python -I parse_bc3.py <bc3_path> <out_dir> <source_tag>
Writes concepts / decompositions / attributes / texts CSVs. Never modifies the input.
"""
import csv, hashlib, os, sys

src, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(src, 'rb').read()
sha = hashlib.sha256(raw).hexdigest()
txt = raw.decode('cp1252', errors='replace')
os.makedirs(out, exist_ok=True)

# Records start with '~' at line start; may span lines.
records, cur = [], None
for line in txt.splitlines():
    if line.startswith('~'):
        if cur is not None:
            records.append(cur)
        cur = line
    elif cur is not None:
        cur += '\n' + line
if cur is not None:
    records.append(cur)

TYPE = {'0': 'other', '1': 'labor', '2': 'machinery', '3': 'material'}
concepts, decomp, attrs, texts, xdefs = [], [], [], [], []
for r in records:
    kind, _, body = r[1], r[2], r[3:]
    f = body.split('|')
    if kind == 'C':
        code = f[0]
        unit, summ, price, date, typ = (f + [''] * 6)[1:6]
        concepts.append(dict(code=code, unit=unit, summary=summ.strip(), price=price.split('\\')[0],
                             price_date_ddmmyy=date.split('\\')[0], bc3_type=typ,
                             bc3_type_label=TYPE.get(typ, 'other'),
                             is_chapter=code.endswith('#'), is_root=code.endswith('##')))
    elif kind == 'D':
        parent = f[0]
        parts = f[1].split('\\') if len(f) > 1 else []
        for i in range(0, len(parts) - 2, 3):
            if parts[i]:
                decomp.append(dict(parent=parent, child=parts[i], factor=parts[i + 1] or '1',
                                   yield_per_unit=parts[i + 2] or '1'))
    elif kind == 'T':
        texts.append(dict(code=f[0], text=(f[1] if len(f) > 1 else '').replace('\r', ' ').replace('\n', ' ').strip()))
    elif kind == 'X':
        code = f[0]
        parts = f[1].split('\\') if len(f) > 1 else []
        if code == '':
            for i in range(0, len(parts) - 2, 3):
                if parts[i]:
                    xdefs.append(dict(attr=parts[i], label=parts[i + 1], unit=parts[i + 2]))
        else:
            for i in range(0, len(parts) - 1, 2):
                if parts[i]:
                    attrs.append(dict(code=code, attr=parts[i], value=parts[i + 1]))

def w(name, rows):
    if not rows:
        return
    p = os.path.join(out, f'{tag}_{name}.csv')
    with open(p, 'w', newline='', encoding='utf-8') as fh:
        cols = ['source_file', 'source_sha256'] + list(rows[0].keys())
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for row in rows:
            wr.writerow({'source_file': os.path.basename(src), 'source_sha256': sha, **row})
    print(p, len(rows))

w('concepts', concepts); w('decompositions', decomp); w('texts', texts)
w('attributes', attrs); w('attribute_definitions', xdefs)
print('records', len(records), 'sha256', sha)
