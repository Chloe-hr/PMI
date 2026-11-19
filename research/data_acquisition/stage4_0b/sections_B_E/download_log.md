# Stage 4.0B (Sections B-E) - download log

Generated 2026-11-19 12:23 UTC. All downloads on 2026-11-19 from public URLs; no logins, CAPTCHAs or paywalls were bypassed.

## Environment at start
- `git status`: clean, branch `research/pmi-hybrid-planning` (HEAD 35be0f8).
- Disk: C: 925G total, 569G free.
- `.venv`: Python 3.14.7 (not modified). `.venv-planning`: Python 3.12.14, OR-Tools 9.15.6755 installed (not modified).
- Section A: `data/raw/candidates/bim_spatial/` empty; no Section A deliverables present.

## Chronological log
1. **CERP** - `codeload.github.com/cerptech/cerp-items-data/tar.gz/9db4fc9...` -> 5,250,749 bytes. Extracted; `sha256sum -c SHA256SUMS`: 525/525 OK.
2. **CYPE** - Public pages inspected (Estructuras > Hormigon armado > Pilares > EHS010). Breakdown visible; BC3 export requires login; legal notice restricts reuse. Not downloaded.
3. **BCCA (upstream of CERP)** - 5 files from `juntadeandalucia.es/.../2024/01/`: BCCA2023_V02.zip (624,785 B), 5.- BCCA23_V02_301023.rar_.zip (10,761,466 B), three PDF listings. Local filenames first saved with `x20` instead of spaces by a decoding bug in the download loop; renamed to the server names (content untouched, hashes recorded after rename). ZIPs extracted; inner `.rar` could not be extracted (no unrar/7-Zip).
4. **BCCA parse** - BC3 decoded as cp1252 (header `ANSI`); 35,476 records -> inspection CSVs. `~X` declares eCO2/ce/m/v/ler but no concept carries values.
5. **BEDEC** - itec.es pages read: subscription; 15 free queries/month after registration; student licences. Not downloaded.
6. **OEKOBAUDAT** - soda4LCA data-stock list; current release OBD_2024_III (13.11.2026). Official `exportCSV` endpoint -> 52,179,438 bytes, ISO-8859-1, `;`-separated. Response headers saved.
7. **EC3** - `buildingtransparency.org/api/materials` -> HTTP 401. Terms: free tier no caching/redistribution. Not downloaded.
8. **PMC7770534** - pmc.ncbi.nlm.nih.gov returned a browser check; full text taken from Europe PMC REST (`PMC7770534/fullTextXML`, CC BY). Data availability: Figshare 10.6084/m9.figshare.12998822.v2.
9. **Figshare 12998822 v2** - metadata JSON + 9 files; MD5 9/9 OK (an initial shell comparison falsely reported mismatches because of a trailing CR; re-verified in Python).
10. **Section E** - searches for linked IFC+schedule, RC productivity, XER, BoQ-vs-actual, revision datasets. RestageIFC (Zenodo 21470658) found to be byte-identical to local `data/raw/Restage_IP_ALL_MULTI_001.ifc` (MD5) - not re-downloaded. DDC CWICR (CC BY-NC) and Frontiers 2025 (on request) not downloaded.

11. **BCCA inner RAR (resumed session)** - 7-Zip 26.06 installed by user. `7z t`: Everything is Ok (5 files, 26,253,092 B). Extracted to new folder `extracted/BCCA23_V02_301023_rar/` (original RAR kept). BC3 and 3 PDFs byte-identical to earlier copies; one new file `BCCA2023_V02.Presto` (13,648,337 B, proprietary). Audit: `bcca_inner_rar_audit.csv`.
12. **Section A check** - checked 2026-11-19 12:23 UTC: data/raw/candidates/bim_spatial/ contains 0 files; no Section A deliverables in research/data_acquisition/stage4_0b/.

## Totals
- Files downloaded/extracted and hashed: 41 (162,407,043 bytes), integrity failures: 0.
- Status counts in `download_manifest.csv`: Downloaded (extracted from archive)=17, Downloaded (extracted from inner RAR with 7-Zip)=5, Downloaded=19, Already available locally=3, Manual download required=1, Restricted=2, Unsuitable=1, Unavailable=1.
