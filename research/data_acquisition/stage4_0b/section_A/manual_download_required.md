# Section A - manual actions

No primary or secondary source required a manual download: all were already local and verified.

Open items that need a person:
1. **SCHEPENDOMLAAN `V_L_Constructief.ifc`** (two local copies, 941,642 B each) - upstream blobs at `OpeningDesign/DataSetSchependomlaan` are empty. Ask the dataset maintainers or the person who first copied the data where these files came from. Until then, exclude them from validation.
2. **`data/raw/4DBenchmarkBim.ifc` + `data/raw/Schedules.xlsx`** - source, licence and authors are undocumented. Record the original URL/paper before citing or publishing results on it.
3. **`data/raw/Models and algorithm for construction scheduling/`** - confirm the Mendeley DOI implied by `GA_mendeley.py` before citing.
4. **Synchro native project** `SCHEPENDOMLAAN/As Planned models/Synchro/*.sp` - proprietary; needs Bentley SYNCHRO to inspect resources or progress, if any.
5. **Reinforcement data** - none of the real models contains rebar. A structural/rebar IFC (e.g. Tekla/Allplan rebar export) of a real RC project is needed before reinforcement mass can be extracted; candidates were not found in this search.

Destination for any new BIM downloads: `data/raw/candidates/bim_spatial/<source>/` (new folder per source).
