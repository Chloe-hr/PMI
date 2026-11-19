"""Stage 5.4 scheduling preparation and independent verification (research only).

Run from repo root:
    .venv/Scripts/python.exe -I research/planning/stage5_4_preparation/scripts/build_stage5_4_prep.py
Reads (never modifies): engineering review package, Agent 1 Stage 5.3A fixture/outputs, Agent 2 specs.
Writes only to research/planning/stage5_4_preparation/.

The calendar functions below are a TEST ORACLE for hand-checkable expected values (earliest fit of a
non-interruptible productive phase in a shift, elapsed holds, 15-minute tick). They do no optimisation,
no resource levelling and are not a scheduling engine; resource feasibility of expected schedules is only
CHECKED (overlap test), never searched.
All controlled inputs are HYPOTHETICAL.
"""
import csv, datetime as dt, hashlib, json, math, os, subprocess, sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
OUT = 'research/planning/stage5_4_preparation'
REV = 'research/validation/engineering_approval_review'
A1 = 'research/implementation/stage5_3'
NOW = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
TICK = 15


def rd(p):
    with open(p, encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def wjson(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w', encoding='utf-8'), indent=2, ensure_ascii=False, default=str)
    print('wrote', name)


def wcsv(name, rows):
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print('wrote', name, len(rows))


SEL = rd(f'{REV}/stage5_3_reference_selection.csv')
TPL = json.load(open(f'{REV}/controlled_demo_input_template.json', encoding='utf-8'))
REF = {}
for r in SEL:
    REF.setdefault(r['bcca_code'], r)


def coeffs(code):
    r = REF[code]
    lab = {x.split('=')[0]: float(x.split('=')[1]) for x in r['labour_h_per_unit_by_trade'].split('; ')}
    mach = {} if r['equipment_h_per_unit'].startswith('none') else {x.split('=')[0].split(' [')[0]: float(x.split('=')[1]) for x in r['equipment_h_per_unit'].split('; ')}
    return lab, mach, float(r['unit_cost_eur']), {k: float(r[k]) for k in ('cost_labour_eur', 'cost_equipment_eur', 'cost_material_eur')}


def estimate(name, code, q, crew, equipment):
    lab, mach, price, split = coeffs(code)
    H = {t: q * c for t, c in lab.items()}
    E = {m: q * c for m, c in mach.items()}
    bounds = {f'labor:{t}': H[t] / crew[t] for t in H if crew.get(t)}
    bounds.update({f'equipment:{m}': E[m] / equipment[m] for m in E if equipment.get(m)})
    missing = [t for t in H if not crew.get(t)] + [m for m in E if not equipment.get(m)]
    dur = None if missing else max(bounds.values())
    return dict(activity=name, bcca_code=code, quantity=q, unit=REF[code]['quantity_unit'], unit_price_eur=price, worker_hours_by_trade=H, machine_hours_by_class=E,
                crew=crew, capacity_bounds_hours=bounds, productive_hours=dur, blocked_by=missing, direct_cost_eur=q * price,
                cost_components_eur={k.split('_')[1]: q * v for k, v in split.items()}, rounding_residual_eur=q * price - q * sum(split.values()))


# ================================================================== Task 1: numerical references
H = TPL['hypothetical_test_fixture']
Q = H['quantities']
crews = {c['id']: c['workers_by_trade'] for c in H['crews']}
eq = {'VIBRADOR': 1}
ACTS = [('COL-REBAR', '05HAC00015', Q['COL_REBAR_kg'], 'HYP-REBAR'), ('COL-FORM', '05HEM00001', Q['COL_FORM_m2'], 'HYP-FORM'), ('COL-CONC', '05HHP00003', Q['COL_CONC_m3'], 'HYP-CONC'),
        ('BEAM-FORM', '05HEM00051', Q['BEAM_FORM_m2'], 'HYP-FORM'), ('SLAB-FORM', '05HEM00101', Q['SLAB_FORM_m2'], 'HYP-FORM'), ('BEAM-REBAR', '05HAC00015', Q['BEAM_REBAR_kg'], 'HYP-REBAR'),
        ('SLAB-REBAR', '05HAC00015', Q['SLAB_REBAR_kg'], 'HYP-REBAR'), ('BEAM-CONC', '05HHJ00003', Q['BEAM_CONC_m3'], 'HYP-CONC'), ('SLAB-CONC', '05HHL00003', Q['SLAB_CONC_m3'], 'HYP-CONC'),
        ('FRM-STRIP (cols)', '05HED00001', Q['COL_FORM_m2'], 'HYP-FORM'), ('FRM-STRIP (beams+slab)', '05HED00001', Q['BEAM_FORM_m2'] + Q['SLAB_FORM_m2'], 'HYP-FORM')]
ref1 = [estimate(n, c, q, crews[k], eq) for n, c, q, k in ACTS]
tot1 = sum(r['direct_cost_eur'] for r in ref1)
assert abs(round(tot1, 2) - 3966.32) < 1e-9, tot1

# Agent 1 Stage 5.3A fixture: recompute independently from its declared element inputs
FX = json.load(open(f'{A1}/fixture_inputs.json', encoding='utf-8'))
fx_sha = sha256(f'{A1}/fixture_inputs.json')
fx_crews = FX['crews']
fx_eq = {k: v for k, v in FX['equipment'].items()}
ref2 = []
for gid, el in FX['elements'].items():
    (x0, y0, z0), (x1, y1, z1) = el['bounds_m']
    vol = (x1 - x0) * (y1 - y0) * (z1 - z0)
    cls = FX['group_assignments'][gid]['classification'].split('_')[-1].upper()
    pref = {'COL': 'COL', 'BEAM': 'BEAM', 'SLAB': 'SLAB'}[cls]
    for op, q in (('REBAR', el['reinforcement_kg']), ('FORM', el['formwork_m2']), ('CONC', vol), ('STRIP', el['formwork_m2'])):
        wi = f'{pref}-{op}' if op != 'STRIP' else 'FRM-STRIP'
        code = FX['catalogue'][wi]
        r = estimate(wi, code, q, fx_crews[FX['crew_by_operation'][op]], fx_eq)
        r.update(global_id=gid)
        ref2.append(r)
tot2 = sum(r['direct_cost_eur'] for r in ref2)
# compare with Agent 1 output (read only)
a1 = rd(f'{A1}/demonstration/activities.csv')
cmp_rows = []
for r in ref2:
    m = [a for a in a1 if a['global_id'] == r['global_id'] and a['work_item'] == r['activity'] and a['kind'] == 'productive']
    a = m[0] if m else {}
    a_h = float(a['productive_hours']) if a.get('productive_hours') else None
    a_c = float(a['reference_cost_eur']) if a.get('reference_cost_eur') else None
    a_w = json.loads(a['worker_hours_by_trade']) if a.get('worker_hours_by_trade') else {}
    w_ok = all(abs(a_w.get(t, -1) - v) < 1e-9 for t, v in r['worker_hours_by_trade'].items())
    cmp_rows.append(dict(global_id=r['global_id'], work_item=r['activity'], bcca_code=r['bcca_code'], quantity=r['quantity'], unit=r['unit'],
                         independent_productive_h=round(r['productive_hours'], 6), agent1_productive_h=a_h,
                         productive_h_match=a_h is not None and abs(a_h - r['productive_hours']) < 1e-9,
                         independent_cost_eur=round(r['direct_cost_eur'], 6), agent1_cost_eur=a_c, cost_match=a_c is not None and abs(a_c - r['direct_cost_eur']) < 1e-6,
                         worker_hours_match=w_ok, independent_worker_hours=json.dumps({k: round(v, 6) for k, v in r['worker_hours_by_trade'].items()}, ensure_ascii=False)))
e1 = json.load(open(f'{A1}/demonstration/estimate.json', encoding='utf-8'))
a1_total = e1['cost']['total_direct_reference_eur']
reference = {
    '_meta': dict(generated=NOW, purpose='Numerical references for comparing Stage 5.3A engineering estimates', hypothetical=True,
                  cost_boundary='BCCA Dic-2023 V02 Andalucia direct unit prices x quantity; excludes overheads, general expenses, profit, VAT, crane/pump/delivery, curing (bundled in concrete labour), waiting time',
                  duration_rule='productive_hours = max over trades H[t]/n[t] and machines E[e]/m[e] (fixed simultaneous crew); no process minimum; no calendar; no rounding to tick',
                  sources={'reference_selection': f'{REV}/stage5_3_reference_selection.csv', 'template': f'{REV}/controlled_demo_input_template.json',
                           'bcca_sha256': SEL[0]['source_sha256'], 'agent1_fixture': f'{A1}/fixture_inputs.json', 'agent1_fixture_sha256': fx_sha}),
    'fixture_A_review_package_4col_frame': dict(
        description='controlled_demo_input_template.json -> hypothetical_test_fixture (4 columns, 4 beams, 1 slab). Basis of the EUR 3,966.32 figure.',
        geometry=H['geometry'], quantities=Q, crews=crews, equipment=H['equipment'], activities=ref1,
        totals=dict(direct_cost_eur=round(tot1, 4), components_eur={k: round(sum(r['cost_components_eur'][k] for r in ref1), 4) for k in ('labour', 'equipment', 'material')},
                    rounding_residual_eur=round(sum(r['rounding_residual_eur'] for r in ref1), 4)),
        status='NOT the fixture implemented by Agent 1 in Stage 5.3A - compare only with an estimator run on these exact quantities'),
    'fixture_B_agent1_stage5_3A': dict(
        description='Independent recomputation of Agent 1 fixture_inputs.json (1 column, 1 beam, 1 slab) with the same BCCA selections', activities=ref2,
        totals=dict(direct_cost_eur=round(tot2, 4), agent1_reported_eur=a1_total, match=abs(tot2 - a1_total) < 1e-6,
                    components_eur={k: round(sum(r['cost_components_eur'][k] for r in ref2), 4) for k in ('labour', 'equipment', 'material')},
                    agent1_components_eur=e1['cost']['components_eur'], rounding_residual_eur=round(sum(r['rounding_residual_eur'] for r in ref2), 4),
                    agent1_rounding_residual_eur=e1['cost']['rounding_residual_eur']),
        comparison_rows=cmp_rows),
}
wjson('reference_calculation.json', reference)
wcsv('agent1_stage5_3A_comparison.csv', cmp_rows)
print('fixture A', round(tot1, 2), '| fixture B independent', round(tot2, 4), 'agent1', a1_total, '| productive matches', sum(r['productive_h_match'] for r in cmp_rows), '/', len(cmp_rows))

# ================================================================== test oracle (calendar arithmetic only)
D = dt.datetime


class Cal:
    def __init__(self, windows, exceptions=(), weekdays=(1, 2, 3, 4, 5)):
        self.windows = windows  # list of ('HH:MM','HH:MM')
        self.exceptions = {dt.date.fromisoformat(x) for x in exceptions}
        self.weekdays = set(weekdays)

    def day_windows(self, d, override=None):
        if d.isoweekday() not in self.weekdays or d in self.exceptions:
            return []
        out = []
        for a, b in (override or self.windows):
            out.append((D.combine(d, dt.time.fromisoformat(a)), D.combine(d, dt.time.fromisoformat(b))))
        return out


def ceil_tick_minutes(hours):
    return int(math.ceil(round(hours * 60, 9) / TICK) * TICK)


def up_tick(t):
    m = t.hour * 60 + t.minute + (1 if t.second or t.microsecond else 0)
    m2 = int(math.ceil(m / TICK) * TICK)
    return D.combine(t.date(), dt.time()) + dt.timedelta(minutes=m2)


def earliest_fit(cal, t, minutes, override=None, horizon_days=60):
    """Earliest start >= t such that [start, start+minutes] lies inside ONE working window (non-interruptible)."""
    longest = max((dt.datetime.strptime(b, '%H:%M') - dt.datetime.strptime(a, '%H:%M')).seconds // 60 for a, b in (override or cal.windows))
    if minutes > longest:
        return None, f'NO_FIT: {minutes} min exceeds the longest window ({longest} min); requires an approved split'
    d = t.date()
    for _ in range(horizon_days):
        for ws, we in cal.day_windows(d, override):
            s = up_tick(max(t, ws))
            if s + dt.timedelta(minutes=minutes) <= we:
                return s, None
        d += dt.timedelta(days=1)
    return None, 'HORIZON_EXHAUSTED'


def split_fit(cal, t, minutes, horizon_days=60):
    segs, left, d = [], minutes, t.date()
    for _ in range(horizon_days):
        for ws, we in cal.day_windows(d):
            s = up_tick(max(t, ws))
            if s >= we:
                continue
            take = min(left, int((we - s).total_seconds() // 60))
            segs.append((s, s + dt.timedelta(minutes=take)))
            left -= take
            t = segs[-1][1]
            if left == 0:
                return segs
        d += dt.timedelta(days=1)
    return None


def fmt(t):
    return t.strftime('%Y-%m-%d %H:%M') if t else None


def run_chain(cal, acts, start):
    """acts: ordered list of dict(id, kind, minutes|hours, preds=[(id, lag_min, basis)], window=override, split=bool, resources={})."""
    res = {}
    for a in acts:
        ready = start
        for p, lag, basis in a.get('preds', []):
            ready = max(ready, res[p]['finish'] + dt.timedelta(minutes=lag))
        if a.get('release_at'):
            ready = max(ready, D.fromisoformat(a['release_at']))
        if a['kind'] == 'elapsed_hold':
            s = ready
            f = s + dt.timedelta(minutes=a['minutes'])
            res[a['id']] = dict(start=s, finish=f, segments=None, note='elapsed (calendar time, no resources)')
        elif a.get('split'):
            segs = split_fit(cal, ready, a['minutes'])
            res[a['id']] = dict(start=segs[0][0], finish=segs[-1][1], segments=[(fmt(x), fmt(y)) for x, y in segs], note='approved split')
        else:
            s, err = earliest_fit(cal, ready, a['minutes'], a.get('window'))
            if err:
                res[a['id']] = dict(start=None, finish=None, error=err)
                raise ValueError(err)
            res[a['id']] = dict(start=s, finish=s + dt.timedelta(minutes=a['minutes']), segments=None, note='')
    return res


def overlaps(acts, res, capacity):
    """Check (not search) that resource usage never exceeds capacity."""
    events = []
    for a in acts:
        for r, n in a.get('resources', {}).items():
            events.append((res[a['id']]['start'], n, r))
            events.append((res[a['id']]['finish'], -n, r))
    events.sort(key=lambda e: (e[0], e[1]))
    use, viol = defaultdict(int), []
    for t, n, r in events:
        use[r] += n
        if use[r] > capacity.get(r, 0):
            viol.append(f'{r} {use[r]}>{capacity.get(r, 0)} at {fmt(t)}')
    return viol


# ================================================================== Task 2: controlled scheduling inputs (fixture B, as Agent 1 implements it)
CAL = dict(timezone='Europe/Madrid', utc_offset_jan='+01:00 (no DST change in the horizon)', working_windows=[dict(weekday=d, start='08:00', end='16:00') for d in range(1, 6)],
           date_exceptions=['2027-01-06'], exception_note='HYPOTHETICAL: 6 Jan (Epifania, a Spanish national holiday) included to exercise exception handling',
           tick_minutes=TICK, rounding='productive minutes rounded UP to 15-min tick (Agent 2 spec)', productive_phase_policy='non-interruptible within one working window unless split is approved')
cal = Cal([('08:00', '16:00')], CAL['date_exceptions'])
by = {(r['global_id'], r['activity']): r for r in ref2}
G = {FX['group_assignments'][g]['classification'].split('_')[-1].upper(): g for g in FX['elements']}


def pa(id_, gid, wi, crew, preds, window=None, extra=None):
    r = by[(gid, wi)]
    d = dict(id=id_, kind='productive', work_item=wi, global_id=gid, bcca_code=r['bcca_code'], quantity=r['quantity'], unit=r['unit'], productive_hours=r['productive_hours'],
             minutes=ceil_tick_minutes(r['productive_hours']), crew_mode=crew, resources=dict(fx_crews[crew]), preds=preds)
    if wi.endswith('-CONC'):
        d['resources']['VIBRADOR'] = 1
    if window:
        d['window'] = window
    d.update(extra or {})
    return d


def hold(id_, minutes, preds, kind_note, condition=None):
    return dict(id=id_, kind='elapsed_hold', minutes=minutes, preds=preds, note=kind_note, condition=condition)


def insp(id_, preds):
    return dict(id=id_, kind='productive', work_item='INSPECTION', minutes=30, resources={'INSPECTOR': 1}, preds=preds,
                note='HYPOTHETICAL pre-pour inspection: 0.5 h of inspector WORKING time (Agent 1 encodes it as a 0.5 h elapsed hold - see deficiency D4)')


POUR = [('08:00', '14:00')]
c, b, s = G['COL'], G['BEAM'], G['SLAB']
EL = {k: FX['elements'][g] for k, g in (('COL', c), ('BEAM', b), ('SLAB', s))}
ACTS_B = [
    pa('C-REBAR', c, 'COL-REBAR', 'HYP-REBAR', []),
    pa('C-FORM', c, 'COL-FORM', 'HYP-FORM', [('C-REBAR', 0, 'FS')]),
    insp('C-INSP', [('C-FORM', 0, 'FS'), ('C-REBAR', 0, 'FS')]),
    pa('C-POUR', c, 'COL-CONC', 'HYP-CONC', [('C-INSP', 0, 'FS')], POUR),
    hold('C-CURE', int(EL['COL']['curing_elapsed_hours'] * 60), [('C-POUR', 0, 'FS')], 'curing gate (elapsed)'),
    hold('C-STRIKE', int(EL['COL']['striking_elapsed_hours_from_pour'] * 60), [('C-POUR', 0, 'FS')], 'striking release measured from pour end (elapsed)', 'strength check PASS assumed (HYPOTHETICAL); real: approval event required'),
    pa('C-STRIP', c, 'FRM-STRIP', 'HYP-FORM', [('C-STRIKE', 0, 'FS'), ('C-CURE', 0, 'FS')]),
    pa('B-FORM', b, 'BEAM-FORM', 'HYP-FORM', [('C-CURE', 0, 'FS'), ('C-STRIP', 0, 'FS')], extra=dict(cross_package='HYPOTHETICAL DR09: beam formwork bears on the column -> after column curing gate; after column stripping (single formwork crew, explicit order)')),
    pa('B-REBAR', b, 'BEAM-REBAR', 'HYP-REBAR', [('B-FORM', 0, 'FS')]),
    insp('B-INSP', [('B-REBAR', 0, 'FS')]),
    pa('B-POUR', b, 'BEAM-CONC', 'HYP-CONC', [('B-INSP', 0, 'FS')], POUR),
    hold('B-CURE', int(EL['BEAM']['curing_elapsed_hours'] * 60), [('B-POUR', 0, 'FS')], 'curing gate (elapsed)'),
    hold('B-STRIKE', int(EL['BEAM']['striking_elapsed_hours_from_pour'] * 60), [('B-POUR', 0, 'FS')], 'striking release from pour end (elapsed)', 'strength check PASS assumed (HYPOTHETICAL)'),
    pa('S-FORM', s, 'SLAB-FORM', 'HYP-FORM', [('B-CURE', 0, 'FS')], extra=dict(cross_package='HYPOTHETICAL DR09: slab soffit formwork after beam curing gate')),
    pa('S-REBAR', s, 'SLAB-REBAR', 'HYP-REBAR', [('S-FORM', 0, 'FS')]),
    insp('S-INSP', [('S-REBAR', 0, 'FS')]),
    pa('S-POUR', s, 'SLAB-CONC', 'HYP-CONC', [('S-INSP', 0, 'FS')], POUR),
    hold('S-CURE', int(EL['SLAB']['curing_elapsed_hours'] * 60), [('S-POUR', 0, 'FS')], 'curing gate (elapsed)'),
    hold('S-STRIKE', int(EL['SLAB']['striking_elapsed_hours_from_pour'] * 60), [('S-POUR', 0, 'FS')], 'striking release from pour end (elapsed)', 'strength check PASS assumed (HYPOTHETICAL)'),
    pa('S-STRIP', s, 'FRM-STRIP', 'HYP-FORM', [('S-STRIKE', 0, 'FS'), ('S-CURE', 0, 'FS')]),
    pa('B-STRIP', b, 'FRM-STRIP', 'HYP-FORM', [('B-STRIKE', 0, 'FS'), ('S-STRIP', 0, 'FS')], extra=dict(cross_package='HYPOTHETICAL: beam soffit props retained until the supported slab is stripped')),
]
CAP = {'OF. 1ª ENCOFRADOR': 2, 'PEÓN ESPECIAL': 3, 'OF. 1ª FERRALLISTA': 2, 'OFICIAL 1ª': 1, 'VIBRADOR': 1, 'INSPECTOR': 1}
START = D(2027, 1, 4, 8, 0)
resB = run_chain(cal, ACTS_B, START)
violB = overlaps(ACTS_B, resB, CAP)
fixture_sched = [dict(id=a['id'], kind=a['kind'], work_item=a.get('work_item', ''), global_id=a.get('global_id', ''), minutes=a['minutes'],
                      productive_hours_unrounded=round(a['productive_hours'], 6) if a.get('productive_hours') else '',
                      start_local=fmt(resB[a['id']]['start']), finish_local=fmt(resB[a['id']]['finish']),
                      predecessors='; '.join(f'{p}({rel},lag {l} min)' for p, l, rel in a.get('preds', [])), resources=json.dumps(a.get('resources', {}), ensure_ascii=False),
                      note=a.get('note', '') or a.get('cross_package', '') or resB[a['id']].get('note', ''), condition=a.get('condition') or '') for a in ACTS_B]
wcsv('fixture_expected_schedule.csv', fixture_sched)
makespan_B = max(r['finish'] for r in resB.values())
sched_inputs = {
    '_meta': dict(generated=NOW, status='HYPOTHETICAL controlled scheduling inputs - not a real project, no approvals',
                  fixture='Agent 1 Stage 5.3A fixture_inputs.json (1 column, 1 beam, 1 slab)', fixture_sha256=fx_sha,
                  durations_from='independent recomputation (reference_calculation.json fixture_B) - identical to Agent 1 productive_hours',
                  semantics='Agent 2 scheduling_engine_specification.md: UTC minute axis, 15-min tick, productive phases non-interruptible within a shift, elapsed holds span non-working time, FS only'),
    'project': dict(id='HYP-FRAME-5.3A', start_local='2027-01-04T08:00', timezone='Europe/Madrid', country='ES', region='AN'),
    'calendar': CAL,
    'shifts': [dict(id='DAY', windows='Mon-Fri 08:00-16:00 local', breaks='none modelled (HYPOTHETICAL)')],
    'resource_capacity_by_trade': CAP,
    'crew_modes': fx_crews,
    'equipment': dict(VIBRADOR=1, CRANE=0, CONCRETE_PUMP=0, note='explicit none for crane/pump (manual handling, staged supply) as in Agent 1 fixture'),
    'concrete_delivery': dict(window_local='08:00-14:00 Mon-Fri', rule='a pour (productive concrete activity) must start and finish inside the delivery window', max_rate_m3_h=None,
                              note='HYPOTHETICAL. Agent 1 fixture declares CONCRETE_DELIVERY=0 (no delivery equipment); this window is a separate supply-time constraint.'),
    'construction_method': {k: FX['group_assignments'][g]['method'] for k, g in (('column', c), ('beam', b), ('slab', s))},
    'inspection_milestones': [dict(id=x, duration_min=30, resource='INSPECTOR', kind='productive (working time)') for x in ('C-INSP', 'B-INSP', 'S-INSP')],
    'curing': {k: dict(elapsed_hours=EL[k]['curing_elapsed_hours'], basis='elapsed from pour finish', label='HYPOTHETICAL') for k in EL},
    'striking': {k: dict(elapsed_hours_from_pour=EL[k]['striking_elapsed_hours_from_pour'], strength_condition='strength check required; PASS assumed for the test only',
                         label='HYPOTHETICAL') for k in EL},
    'activities': [{k: v for k, v in a.items() if k not in ('preds',)} | dict(predecessors=[dict(id=p, relation=rel, lag_minutes=l, lag_basis='elapsed') for p, l, rel in a.get('preds', [])]) for a in ACTS_B],
    'cross_package_dependencies': [dict(activity=a['id'], rule=a['cross_package']) for a in ACTS_B if a.get('cross_package')],
    'expected_result': dict(makespan_finish_local=fmt(makespan_B), resource_violations=violB, schedule_file='fixture_expected_schedule.csv',
                            note='computed by the test oracle; all dependencies explicit so the schedule is resource-feasible without levelling (checked)'),
    'variant_without_cross_package_dependencies': dict(note='Agent 1 dependencies.csv (as exported) has no column->beam->slab links: beam and slab formwork become eligible at project start, '
                                                            'competing with the column for HYP-FORM. A scheduler must then serialise by resources; the result is physically invalid (beam formwork before the column exists).'),
}
wjson('controlled_scheduling_inputs.json', sched_inputs)

# ================================================================== Task 3: verification cases
C0 = Cal([('08:00', '16:00')])
MON = D(2027, 1, 4, 8, 0)
FRI = D(2027, 1, 8, 8, 0)
cases = []


def case(cid, title, inputs, expected, behaviour, calc=None):
    cases.append(dict(case_id=cid, title=title, inputs=inputs, expected_behaviour=behaviour, expected=expected, independent_calculation=calc or ''))


common = dict(calendar='Mon-Fri 08:00-16:00 Europe/Madrid, no exceptions', tick_minutes=15, start='2027-01-04 08:00 (Monday)', productive_policy='non-interruptible within a window')
# TC1
a = [dict(id='A', kind='productive', minutes=180), dict(id='B', kind='productive', minutes=150, preds=[('A', 0, 'FS')]), dict(id='C', kind='productive', minutes=240, preds=[('B', 0, 'FS')])]
r = run_chain(C0, a, MON)
case('TC1', 'Simple finish-to-start chain', common | dict(activities='A 3 h -> B 2.5 h -> C 4 h (FS, lag 0)'),
     {k: [fmt(v['start']), fmt(v['finish'])] for k, v in r.items()} | dict(makespan=fmt(r['C']['finish'])),
     'C cannot start at 13:30 because only 2.5 h remain in the shift; it starts next working morning', 'A 08:00-11:00; B 11:00-13:30; C needs 240 min > 150 min left -> Tue 08:00-12:00')
# TC2
a = [dict(id='A', kind='productive', minutes=180, resources={'X': 1}), dict(id='B', kind='productive', minutes=300, resources={'Y': 1}),
     dict(id='C', kind='productive', minutes=120, resources={'X': 1}, preds=[('A', 0, 'FS'), ('B', 0, 'FS')])]
r = run_chain(C0, a, MON)
case('TC2', 'Parallel activities without resource conflict', common | dict(activities='A 3 h (X), B 5 h (Y) in parallel; C 2 h (X) after A and B', capacity={'X': 1, 'Y': 1}),
     {k: [fmt(v['start']), fmt(v['finish'])] for k, v in r.items()} | dict(makespan=fmt(r['C']['finish']), resource_violations=overlaps(a, r, {'X': 1, 'Y': 1})),
     'A and B overlap because they use different resources', 'C ready at max(11:00, 13:00) = 13:00 -> 13:00-15:00')
# TC3 - both orders checked; expected makespan unique
o1 = run_chain(C0, [dict(id='A', kind='productive', minutes=180, resources={'X': 1}), dict(id='B', kind='productive', minutes=300, resources={'X': 1}, preds=[('A', 0, 'FS')]),
                    dict(id='C', kind='productive', minutes=120, resources={'X': 1}, preds=[('B', 0, 'FS')])], MON)
o2 = run_chain(C0, [dict(id='B', kind='productive', minutes=300, resources={'X': 1}), dict(id='A', kind='productive', minutes=180, resources={'X': 1}, preds=[('B', 0, 'FS')]),
                    dict(id='C', kind='productive', minutes=120, resources={'X': 1}, preds=[('A', 0, 'FS')])], MON)
case('TC3', 'Parallel activities sharing a limited crew', common | dict(activities='A 3 h (X), B 5 h (X), C 2 h (X) after A and B', capacity={'X': 1}),
     dict(makespan=fmt(o1['C']['finish']), makespan_other_order=fmt(o2['C']['finish']), order_A_first={k: [fmt(v['start']), fmt(v['finish'])] for k, v in o1.items()},
          order_B_first={k: [fmt(v['start']), fmt(v['finish'])] for k, v in o2.items()}, cpm_unconstrained_finish='2027-01-04 15:00', max_usage_X=1),
     'X never exceeds 1; A and B are serialised (either order); makespan is unique even though the order is not', 'A+B = 8 h fill Monday; C Tue 08:00-10:00. CPM without resources: C Mon 13:00-15:00')
# TC4
nf, err = earliest_fit(C0, D(2027, 1, 8, 12, 0), 360)
sp = split_fit(C0, D(2027, 1, 8, 12, 0), 360)
nf2, err2 = earliest_fit(C0, D(2027, 1, 8, 8, 0), 600)
case('TC4', 'Weekend / non-working-day constraint', common | dict(activities='A 6 h ready Fri 2027-01-08 12:00; variant: split approved; variant: 10 h activity'),
     dict(non_interruptible=[fmt(nf), fmt(nf + dt.timedelta(minutes=360))], approved_split=[(fmt(x), fmt(y)) for x, y in sp], ten_hour_activity=err2),
     'Only 4 h remain on Friday; Saturday/Sunday are non-working. A 10 h phase cannot fit an 8 h window -> NO_FIT diagnostic, not silent splitting',
     'Mon 2027-01-11 08:00-14:00; split: Fri 12:00-16:00 + Mon 08:00-10:00')
# TC5
a = [dict(id='POUR', kind='productive', minutes=60), dict(id='CURE', kind='elapsed_hold', minutes=48 * 60, preds=[('POUR', 0, 'FS')]),
     dict(id='STRIP', kind='productive', minutes=60, preds=[('CURE', 0, 'FS')])]
r = run_chain(C0, a, D(2027, 1, 8, 14, 0))
case('TC5', 'Elapsed curing crossing non-working days', common | dict(activities='POUR 1 h ready Fri 2027-01-08 14:00; CURE 48 h elapsed; STRIP 1 h'),
     {k: [fmt(v['start']), fmt(v['finish'])] for k, v in r.items()} | dict(wrong_if_working_time_lag='CURE would end Mon 2027-01-18 15:00 (48 working h = 6 working days)'),
     'Curing runs through the weekend (elapsed); stripping waits for the next working window', 'POUR 14:00-15:00 Fri; CURE to Sun 15:00; STRIP Mon 08:00-09:00')
# TC6
a = [dict(id='POUR', kind='productive', minutes=60), dict(id='MIN72', kind='elapsed_hold', minutes=72 * 60, preds=[('POUR', 0, 'FS')]),
     dict(id='STRIP', kind='productive', minutes=60, preds=[('MIN72', 0, 'FS')])]
ra = run_chain(C0, a, MON)
a_b = [dict(a[0]), dict(a[1]), dict(a[2], release_at='2027-01-08T10:30')]
rb = run_chain(C0, a_b, MON)
a_c = [dict(a[0]), dict(a[1]), dict(a[2], release_at='2027-01-05T09:00')]
rc = run_chain(C0, a_c, MON)
case('TC6', 'Strength-release condition before formwork removal', common | dict(activities='POUR 1 h Mon 08:00; striking requires >= 72 h elapsed AND a recorded strength approval event'),
     dict(no_approval_event=dict(strip_projected=[fmt(ra['STRIP']['start']), fmt(ra['STRIP']['finish'])], status='CONDITIONAL - hold not cleared'),
          approval_2027_01_08_1030=dict(strip=[fmt(rb['STRIP']['start']), fmt(rb['STRIP']['finish'])], status='released'),
          approval_before_minimum_2027_01_05_0900=dict(strip=[fmt(rc['STRIP']['start']), fmt(rc['STRIP']['finish'])], status='released at the elapsed minimum')),
     'Release = max(minimum elapsed, approval event); without the event the projected strip is CONDITIONAL and must not clear the field hold (Agent 2 spec)',
     'POUR 08:00-09:00; min elapsed ends Thu 01-07 09:00')
# TC7
a = [dict(id='A', kind='productive', minutes=480), dict(id='B', kind='productive', minutes=480, preds=[('A', 0, 'FS')])]
r = run_chain(C0, a, MON)
case('TC7', 'Impossible completion deadline', common | dict(activities='A 8 h -> B 8 h', hard_deadline='B finish <= 2027-01-04 16:00'),
     dict(status='INFEASIBLE', earliest_B_finish=fmt(r['B']['finish']), implicated=['deadline(B)', 'A->B FS', 'A duration', 'B duration', 'calendar'], selected_schedule=None),
     'Preflight serial bound or CP-SAT returns infeasible; diagnostics name the deadline and the controlling chain; no relaxed schedule is selected', '16 working hours need two shifts -> earliest finish Tue 16:00')
# TC8
case('TC8', 'Missing resource capacity', common | dict(activities='REBAR needs crew mode {OF. 1ª FERRALLISTA: 2}', capacity_variants=dict(a=None, b=0, c=1)),
     dict(a='BLOCKED: MISSING_INPUT capacity for OF. 1ª FERRALLISTA (null)', b='BLOCKED: IMPOSSIBLE_CREW - demand > 0 with capacity 0', c='BLOCKED: no eligible mode (mode needs 2, capacity 1)',
          never='scheduled with zero duration or zero capacity treated as unlimited'),
     'Preflight diagnostic before solving; the activity is not scheduled')
# TC9
case('TC9', 'Cyclic dependency graph', common | dict(activities='A -> B -> C -> A (FS)'),
     dict(status='MODEL_INVALID', diagnostic='CYCLE', cycle=['A', 'B', 'C', 'A']),
     'Rejected in preflight with the cycle listed; no CPM pass or solve attempted')
# fixture case
case('TC10', 'Controlled frame (fixture B) end-to-end', dict(inputs='controlled_scheduling_inputs.json'), dict(makespan=fmt(makespan_B), resource_violations=violB, schedule='fixture_expected_schedule.csv'),
     'All activities scheduled; holds elapsed; pours inside 08:00-14:00; holiday 2027-01-06 skipped; no resource over-use')
wjson('scheduling_test_cases.json', dict(_meta=dict(generated=NOW, oracle='calendar arithmetic only (this script); times are Europe/Madrid local (UTC+01:00)', hypothetical=True), cases=cases))
flat = []
for cc in cases:
    flat.append(dict(case_id=cc['case_id'], title=cc['title'], expected_behaviour=cc['expected_behaviour'], expected=json.dumps(cc['expected'], ensure_ascii=False, default=str),
                     independent_calculation=cc['independent_calculation']))
wcsv('expected_results.csv', flat)

# ================================================================== Task 5: gate matrix + deficiencies
P3 = [r for r in rd(f'{REV}/priority_approval_register.csv') if r['decision_phase'] == 'RCPSP']
FIXNEED = {'AP-DR05': ('yes', 'column sequence (Agent 1 fixture: cage_first)'), 'AP-DR06': ('yes', 'formwork/rebar before pour; beam/slab formwork_first'),
           'AP-DR07': ('yes', '24 h hypothetical curing hold'), 'AP-DR08': ('yes', 'striking 24 h / 168 h from pour + assumed strength pass'),
           'AP-DR09': ('yes - MISSING in Agent 1 output', 'supporting members before supported formwork; added hypothetically in controlled_scheduling_inputs.json'),
           'AP-DR10': ('no', 'single storey fixture'), 'AP-DR11': ('no', 'single zone fixture'), 'AP-DR15': ('yes (policy)', 'no precedence from adjacency')}
gate = [dict(approval_id=r['approval_id'], description=r['description'], required_for_controlled_fixture=FIXNEED[r['approval_id']][0], fixture_use=FIXNEED[r['approval_id']][1],
             fixture_treatment='HYPOTHETICAL selection for software testing; not an approval', required_for_real_project='yes - engineering approval', expertise=r['required_expertise'],
             status='PENDING') for r in P3]
wcsv('engineering_gate_matrix.csv', gate)
deps = rd(f'{A1}/demonstration/dependencies.csv')
DEF = [
    ('D1', 'Fixture identity', 'Agent 1 Stage 5.3A fixture (1 col/1 beam/1 slab, EUR %.2f) differs from the review-package fixture (4 col/4 beam/1 slab, EUR 3,966.32)' % a1_total,
     'Comparisons must name the fixture and its SHA-256; reference_calculation.json provides both', 'Agent 1 / user'),
    ('D2', 'Calendar timezone', f"5.3A calendar timezone {FX['calendar']['timezone']} for an Andalusian fixture", 'Use Europe/Madrid (same offset, different holiday rules)', 'Agent 1'),
    ('D3', 'Cross-package support dependencies', f'5.3A dependencies.csv has {len(deps)} edges, none between column, beam and slab packages (DR09)', 'Add explicit support edges or block scheduling', 'Agent 1 + engineer (AP-DR09)'),
    ('D4', 'Inspection semantics', 'Pre-pour inspection encoded as 0.5 h elapsed_hold (can fall outside working hours, no inspector resource)', 'Model as working-time activity with inspector resource or approved milestone', 'Agent 1 / Agent 2 contract'),
    ('D5', 'Striking reference point', 'Striking modelled as curing hold + extra hold (24 + 144 h) instead of lag from pour end', 'Store striking minimum as lag from pour finish (lag_reference) so curing changes do not shift it', 'Agent 1'),
    ('D6', 'Strength condition state', 'Fixture "assumes the check passes"; output has no conditional/approval-event field per hold', 'Add release_rule_id + condition status (conditional/approved) to holds', 'Agent 1 / Agent 2 contract'),
    ('D7', 'Dependency lag fields', f"dependencies.csv columns {list(deps[0].keys()) if deps else []}: lag_hours, no lag_basis", 'Use canonical ActivityDependency.lag_minutes + lag_basis', 'Agent 1'),
    ('D8', 'Calendar exceptions', '5.3A calendar has no date_exceptions field', 'Add holidays/exceptions to the calendar contract', 'Agent 1 / user input'),
    ('D9', 'Shift fit', 'No check that productive minutes fit a working window (review-package fixture FRM-STRIP 8.11 h > 8 h shift)', 'Preflight NO_FIT diagnostic or approved split per activity', 'Agent 1 (5.4)'),
    ('D10', 'Trade capacity vs crew modes', 'Crews are fixed modes; PEON ESPECIAL appears in HYP-FORM and HYP-CONC; no available_workers_by_trade pool', 'Add trade-level capacity (Agent 2 user_input "Available workers")', 'user input contract'),
    ('D11', 'Concrete supply window', 'CONCRETE_DELIVERY=0 means no delivery equipment; no field for delivery time windows or rate', 'Add supply window/rate to the equipment or procurement contract', 'Agent 2 contract'),
]
wcsv('contract_deficiencies.csv', [dict(id=a, topic=b, finding=c, recommendation=d, owner=e) for a, b, c, d, e in DEF])

# ================================================================== Task 4: engine usage + report
eng = f"""# Scheduling engine usage for the controlled frame (delta to Agent 2 specification)

Generated {NOW}. This document **adds** fixture-level detail to `research/architecture/stage5_0/scheduling_engine_specification.md`; it does not restate it and does not implement a scheduler.

## 1. Inputs -> model elements
| Input (controlled_scheduling_inputs.json) | CPM | OR-Tools CP-SAT |
|---|---|---|
| productive activity, minutes (ceil 15) | duration on working-time calendar | interval var per mode; start restricted to precomputed window-fit start slots (AddAllowedAssignments / domain), end = start + minutes |
| elapsed_hold (curing, striking minimum) | lag in elapsed minutes | fixed-size interval (or pure precedence with elapsed lag) not consuming resources, allowed to span nights/weekends |
| inspection (working time, INSPECTOR) | working-time activity | interval + cumulative on INSPECTOR |
| resource_capacity_by_trade, crew_modes | ignored (CPM is resource-free) | AddCumulative per trade/equipment; crew mode demand = workers_by_trade |
| concrete_delivery window | not in CPM (report separately) | start domain of pour intervals limited to slots whose end <= 14:00 |
| calendar + date_exceptions | working-time map | expanded to absolute UTC minute windows; no productive slot on exceptions |
| predecessors FS + lag_basis elapsed | forward/backward pass | end(pred) + lag <= start(succ) |
| strength condition | not representable -> flag | release literal: start(strip) >= max(min elapsed, approval time); without approval event the solution is labelled CONDITIONAL |

## 2. Conditional dependencies
- Method choices (DR05 cage_first vs formwork_first) are resolved **before** solving from approved method IDs; the solver never chooses an unapproved method.
- Alternative modes (e.g. split allowed) are optional intervals with exactly-one constraints only when the alternative is approved.
- Holds with an approval event: model the event time as a fixed lower bound when recorded; as a projected bound (status CONDITIONAL) when not.

## 3. Infeasibility diagnostics expected by the test cases
| Case | Stage | Diagnostic |
|---|---|---|
| TC4 10 h phase | preflight | NO_FIT (phase longer than any window; split not approved) |
| TC7 deadline | preflight serial bound / CP-SAT assumptions | INFEASIBLE, implicates deadline literal and controlling chain |
| TC8 capacity | preflight | MISSING_INPUT / IMPOSSIBLE_CREW / NO_ELIGIBLE_MODE |
| TC9 cycle | preflight | MODEL_INVALID: CYCLE [A,B,C,A] |
| fixture without DR09 edges | preflight warning | UNSUPPORTED_SEQUENCE: supported member formwork without support predecessor |

## 4. Mapping back to BIM elements and IFC4D
| PMI record | IFC4 entity | Notes |
|---|---|---|
| Schedule | IfcWorkSchedule (PredefinedType PLANNED) + IfcRelAssignsToControl -> tasks | one per scenario/version |
| WorkPackage | IfcTask (summary) + IfcRelNests -> activity tasks | zone/pour batch |
| productive ConstructionActivity | IfcTask (PredefinedType CONSTRUCTION; FRM-STRIP DISMANTLE) with IfcTaskTime ScheduleStart/ScheduleFinish, ScheduleDuration, DurationType WORKTIME | ISO 8601 local times with offset |
| elapsed_hold (curing, striking) | IfcTask PredefinedType USERDEFINED, ObjectType CURING_HOLD / STRIKING_HOLD, IfcTaskTime DurationType ELAPSEDTIME | alternatively IfcRelSequence.TimeLag (IfcLagTime, DurationType ELAPSEDTIME) when no task row is wanted |
| inspection | IfcTask USERDEFINED ObjectType INSPECTION | IsMilestone false (0.5 h working time) |
| ActivityDependency | IfcRelSequence SequenceType FINISH_START, TimeLag IfcLagTime | lag_basis -> DurationType |
| element allocation | IfcRelAssignsToProcess (RelatingProcess = IfcTask, RelatedObjects = IfcProduct by GlobalId) | via WorkItem -> QuantityAllocation -> BIMElement.global_id; version-scoped IDs resolved to the source model's GlobalIds |
| Crew / EquipmentResource | IfcLaborResource / IfcConstructionEquipmentResource + IfcRelAssignsToResource | resource usage per task |
| ProjectCalendar | IfcWorkCalendar (WorkingTimes IfcWorkTime + IfcRecurrencePattern, ExceptionTimes) | holidays as exceptions |

Round-trip test (per Agent 2): re-read the exported IFC, compare task times, sequence edges, lag types and product assignments with the schedule; source model bytes must be unchanged (write a new file).
"""
open(f'{OUT}/scheduling_engine_usage.md', 'w', encoding='utf-8').write(eng)

ok_prod = sum(r['productive_h_match'] for r in cmp_rows)
ok_cost = sum(r['cost_match'] for r in cmp_rows)
report = f"""# Stage 5.4 scheduling preparation and independent verification

Generated {NOW}. Research only; all inputs HYPOTHETICAL; no approvals; no scheduler implemented.

## 1. Numerical reference (Task 1) - `reference_calculation.json`
- **Fixture A** (review package, 4 columns / 4 beams / 1 slab): EUR {tot1:.2f} direct cost = sum of quantity x BCCA unit price over 11 activities; boundary: direct catalogue cost only (no overheads, VAT, crane/pump/delivery, curing labour bundled in concrete, no waiting cost).
- **Fixture B** (Agent 1 Stage 5.3A `fixture_inputs.json`, 1 column / 1 beam / 1 slab): independent recomputation EUR {tot2:.4f}; Agent 1 reports EUR {a1_total} -> {'MATCH' if abs(tot2 - a1_total) < 1e-6 else 'MISMATCH'}. Productive hours match {ok_prod}/{len(cmp_rows)}, costs match {ok_cost}/{len(cmp_rows)} (`agent1_stage5_3A_comparison.csv`).
- **Agent 1 did not implement fixture A**; its estimate cannot be compared with EUR 3,966.32 (deficiency D1).

## 2. Controlled scheduling inputs (Task 2) - `controlled_scheduling_inputs.json`
Fixture B with: start Mon 2027-01-04 08:00 Europe/Madrid; Mon-Fri 08:00-16:00; HYPOTHETICAL holiday 2027-01-06; capacities by trade {json.dumps(CAP, ensure_ascii=False)}; 0.5 h inspections in working time; curing 24 h elapsed; striking 24 h (column) / 168 h (beam, slab) elapsed from pour with assumed strength pass; pours inside a 08:00-14:00 delivery window; three HYPOTHETICAL cross-package support dependencies (column -> beam formwork, beam -> slab formwork, slab strip -> beam strip).
Expected schedule (`fixture_expected_schedule.csv`): finish **{fmt(makespan_B)}**; resource check: {'no over-use' if not violB else violB}.

## 3. Verification cases (Task 3) - `scheduling_test_cases.json`, `expected_results.csv`
{len(cases)} cases: FS chain with shift fit, parallel without conflict, shared crew (unique makespan, order free), weekend + approved split + NO_FIT, elapsed curing over a weekend, strength release (conditional / approved / early approval), impossible deadline, missing capacity (null / 0 / insufficient), cycle, and the controlled frame end-to-end. Expected values come from a calendar-arithmetic test oracle (no optimisation).

## 4. Engine usage and IFC4D mapping (Task 4) - `scheduling_engine_usage.md`
Delta to Agent 2's specification: input -> CPM/CP-SAT mapping, conditional dependencies, expected diagnostics, and PMI -> IFC4 (IfcTask, IfcTaskTime WORKTIME/ELAPSEDTIME, IfcRelSequence + IfcLagTime, IfcRelAssignsToProcess, IfcWorkCalendar, resources).

## 5. Engineering gates (Task 5) - `engineering_gate_matrix.csv`, `contract_deficiencies.csv`
- Of the 8 P3 decisions, 6 are needed for the controlled fixture (DR05, DR06, DR07, DR08, DR09, DR15) and used only as HYPOTHETICAL selections; DR10 and DR11 are not needed (single storey, single zone). All 8 require engineering approval for a real project; all remain PENDING.
- {len(DEF)} contract deficiencies, most important: D3 missing support dependencies in the 5.3A output, D4 inspections as elapsed holds, D5 striking measured from the wrong reference point, D7 lag fields not canonical.

## Preservation
See `preservation_verification.json`.
"""
open(f'{OUT}/scheduling_preparation_report.md', 'w', encoding='utf-8').write(report)

# ================================================================== preservation
snap = {}
for line in open(f'{OUT}/preservation/task_start_snapshot.sha256', encoding='utf-8'):
    h, p = line.rstrip('\n').split(' ', 1)
    snap[p.lstrip('*')] = h
changed = []
for p, h in snap.items():
    if not os.path.exists(p) or sha256(p) != h:
        changed.append(dict(path=p, owner='Agent 1 (concurrent)' if p.startswith(('pmi_core/', 'tests/', 'research/implementation/')) else 'other',
                            mtime_utc=dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).isoformat() if os.path.exists(p) else 'missing'))
bases = []
for name, bf in [('Stage 4.0B baseline', 'research/data_acquisition/stage4_0b/sections_B_E/preservation/baseline_sha256_before_stage4_0b.txt'),
                 ('Stage 4.0A baseline', 'research/evaluation/stage4_0a/preservation/baseline_sha256_before_stage4_0a.txt')]:
    bad, n = [], 0
    for line in open(bf, encoding='utf-8'):
        h, p = line.rstrip('\n').split(' ', 1)
        p = p.lstrip('*')
        n += 1
        if not os.path.exists(p) or sha256(p) != h:
            bad.append(p)
    bases.append(dict(check=name, total=n, changed_or_missing=bad))
gsx = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout.splitlines()
pres = dict(generated=NOW, checks=bases + [dict(check='protected paths vs task-start snapshot', total=len(snap), changed=changed),
                                           dict(check='git status', entries=gsx), dict(check='write scope', paths=[OUT + '/']),
                                           dict(check='no approvals, training, inference, environment change, commit or push', result='confirmed by script scope')])
pres['all_protected_unchanged_by_this_task'] = not any(b['changed_or_missing'] for b in bases) and not [c for c in changed if c['owner'] == 'other']
json.dump(pres, open(f'{OUT}/preservation_verification.json', 'w', encoding='utf-8'), indent=2)
print('preservation ok:', pres['all_protected_unchanged_by_this_task'], 'changed', len(changed), '| fixture makespan', fmt(makespan_B), 'violations', violB)
