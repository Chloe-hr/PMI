"""Read-only profile of the Thiele et al. (2020) Figshare workbooks.
Usage: python -I profile_thiele.py <original_dir> <out_csv>
Counts only; no merging, no labels, no fitting.
"""
import csv, glob, hashlib, os, sys
import openpyxl

def idx(h, *names):
    low = [str(c).strip().lower() if c is not None else '' for c in h]
    for n in names:
        if n.lower() in low:
            return low.index(n.lower())
    raise ValueError(f'none of {names} in header')

def hdr_row(rows, first):
    for k, x in enumerate(rows[:6]):
        cells = [str(c).strip().lower() for c in (x or []) if c is not None]
        if first.lower() in cells and 'quantity' in cells:
            return k
    raise ValueError('header not found')

src, out = sys.argv[1], sys.argv[2]
rows = []
for f in sorted(glob.glob(os.path.join(src, '*.xlsx'))):
    sha = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    names = [ws.title for ws in wb.worksheets]
    r = dict(file=os.path.basename(f), sha256=sha, sheets='|'.join(names))

    # Program Links: planned network
    pl = list(wb['Program Links'].iter_rows(values_only=True))
    h = list(pl[0])
    iD = idx(h, 'Duration')
    iP = idx(h, 'Predecessors', 'WBS Predecessors', 'Predessors')
    tasks = [x for x in pl[1:] if x and x[0] is not None]
    r['program_tasks'] = len(tasks)
    r['program_tasks_duration_gt0'] = sum(1 for x in tasks if isinstance(x[iD], (int, float)) and x[iD] > 0)
    npred = 0
    for x in tasks:
        p = x[iP]
        if p is None or str(p).strip() == '':
            continue
        npred += len([t for t in str(p).split(',') if t.strip()])
    r['program_predecessor_links'] = npred
    r['program_progress_claim_columns'] = sum(1 for c in h if isinstance(c, str) and c.startswith('%C') or hasattr(c, 'year'))
    r['program_duration_values_nonint'] = sum(1 for x in tasks if isinstance(x[iD], float) and not float(x[iD]).is_integer())

    # Estimate: resource lines with production rates
    es = list(wb['Estimate'].iter_rows(values_only=True))
    k0 = hdr_row(es, 'Type')
    eh = list(es[k0])
    iT, iPr, iQ, iDu = idx(eh, 'Type'), idx(eh, 'Prodn', 'Production'), idx(eh, 'Quantity'), idx(eh, 'Duration')
    r['estimate_header_row'] = k0 + 1
    es = es[k0 - 1:] if k0 >= 1 else [None] + es
    lines = [x for x in es[2:] if x and isinstance(x[iT], str) and x[iT].strip() in ('L', 'P', 'M', 'S')]
    r['estimate_resource_lines'] = len(lines)
    for t, lab in (('L', 'labour'), ('P', 'plant'), ('M', 'material'), ('S', 'subcontract')):
        r[f'estimate_{lab}_lines'] = sum(1 for x in lines if x[iT].strip() == t)
    r['estimate_lines_with_prodn'] = sum(1 for x in lines if isinstance(x[iPr], (int, float)))
    r['estimate_items_with_duration'] = sum(1 for x in es[2:] if x and isinstance(x[iDu], (int, float)) and x[iDu] > 0)

    # Portfolio WBS: planned vs actual quantities/costs per cost account
    pw = list(wb['Portfolio WBS'].iter_rows(values_only=True))
    hdr = None
    for k, x in enumerate(pw[:5]):
        if x and x[0] in ('Portfolio WBS', 'Cost Code'):
            hdr = k
    acc = [x for x in pw[hdr + 2:] if x and isinstance(x[0], (int, float))]
    r['portfolio_wbs_accounts'] = len(acc)
    iFQ, iFC = idx(pw[hdr], 'Final Qty'), idx(pw[hdr], 'Final Cost')
    r['accounts_with_final_qty'] = sum(1 for x in acc if isinstance(x[iFQ], (int, float)) and x[iFQ] > 0)
    r['accounts_with_final_cost'] = sum(1 for x in acc if isinstance(x[iFC], (int, float)) and x[iFC] > 0)
    r['monthly_periods'] = sum(1 for c in pw[hdr] if hasattr(c, 'year'))

    # Actual costs: dated lines
    ac = list(wb['Actual Costs'].iter_rows(values_only=True))
    dated = [x for x in ac[1:] if x and hasattr(x[0], 'year')]
    r['actual_cost_lines_dated'] = len(dated)
    if dated:
        r['actual_cost_first_date'] = min(x[0] for x in dated).date().isoformat()
        r['actual_cost_last_date'] = max(x[0] for x in dated).date().isoformat()
    r['activity_actual_start_finish_fields'] = 'none found'
    rows.append(r)

os.makedirs(os.path.dirname(out), exist_ok=True)
keys = []
for r in rows:
    for k in r:
        if k not in keys:
            keys.append(k)
with open(out, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
for r in rows:
    print(r)
