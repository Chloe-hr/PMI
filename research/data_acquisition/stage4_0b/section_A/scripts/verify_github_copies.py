"""Compare local copies of GitHub repositories with the upstream default-branch tree.

Usage: python -I verify_github_copies.py <out_csv> owner/repo=local_dir [...]
Uses `gh api` for the tree and git blob hashing (sha1 of 'blob <size>\\0' + content)
for local files. Read-only on local data. Also flags Git LFS pointer files.
"""
import csv, hashlib, json, os, subprocess, sys

out = sys.argv[1]
rows = []
for spec in sys.argv[2:]:
    repo, local = spec.split('=', 1)
    meta = json.loads(subprocess.run(['gh', 'api', f'repos/{repo}'], capture_output=True, text=True).stdout)
    br = meta['default_branch']
    commit = json.loads(subprocess.run(['gh', 'api', f'repos/{repo}/commits/{br}'], capture_output=True, text=True).stdout)
    tree = json.loads(subprocess.run(['gh', 'api', f'repos/{repo}/git/trees/{commit["sha"]}?recursive=1'], capture_output=True, text=True).stdout)
    remote = {t['path']: t for t in tree['tree'] if t['type'] == 'blob'}
    loc = {}
    for dp, _, fs in os.walk(local):
        for fn in fs:
            p = os.path.join(dp, fn)
            loc[os.path.relpath(p, local).replace('\\', '/')] = p
    for path in sorted(set(remote) | set(loc)):
        r, p = remote.get(path), loc.get(path)
        st, lfs = '', False
        if p:
            data = open(p, 'rb').read()
            lfs = data.startswith(b'version https://git-lfs')
            bh = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
            if r is None:
                st = 'local only'
            elif bh == r['sha']:
                st = 'identical to upstream'
            else:
                # zip downloads may normalise line endings; try CRLF->LF
                d2 = data.replace(b'\r\n', b'\n')
                st = 'identical after CRLF->LF' if hashlib.sha1(b'blob %d\0' % len(d2) + d2).hexdigest() == r['sha'] else 'differs from upstream'
        else:
            st = 'missing locally'
        if path.lower().endswith('.ifc') or st != 'identical to upstream':
            rows.append(dict(repo=repo, default_branch=br, upstream_commit=commit['sha'], upstream_commit_date=commit['commit']['committer']['date'],
                             licence=(meta.get('license') or {}).get('spdx_id'), path=path, local_path=(p or '').replace('\\', '/'),
                             local_bytes=os.path.getsize(p) if p else '', upstream_bytes=r['size'] if r else '', status=st, lfs_pointer=lfs))
    n = sum(1 for k in remote if k in loc)
    print(repo, commit['sha'][:10], 'remote blobs', len(remote), 'local files', len(loc), 'in both', n, 'truncated', tree.get('truncated'))
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'w', newline='', encoding='utf-8') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
from collections import Counter
print(Counter((r['repo'], r['status']) for r in rows))
print('lfs pointers', sum(r['lfs_pointer'] for r in rows))
