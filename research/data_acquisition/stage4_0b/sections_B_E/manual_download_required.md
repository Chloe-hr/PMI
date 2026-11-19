# Manual actions required (Sections B-E)

None of these were attempted with credentials. Destination folders already exist or must be created by the user.

## 1. ITeC BEDEC - Catalonia prices, productivity justifications and environmental indicators
- **Website:** https://itec.es/servicios/bedec/ (metabase), shop: https://tienda.itec.es/categoria-producto/bedec-es/
- **Access:** paid subscription (monthly/annual: "BEDEC Proyecto y obra", "BEDEC Sostenibilidad"); free community registration gives 15 queries/month; free student licence via https://itec.es/servicios/licencias/ (requires school agreement, professor approval and enrolment PDF).
- **Relevant content:** "Justificaciones de partidas de obra" (labour/machinery/material breakdown), Catalonia/Barcelona prices; environmental indicators (CO2, energy, waste, recycled content, water; 13 indicators in Sostenibilidad tier).
- **Steps:** (1) obtain licence (student route recommended for research); (2) log in to the BEDEC web; (3) select Barcelona territory and current edition; (4) build a selection of structural chapters (foundations, RC structure, earthworks, masonry) matching the 18 target items in `productivity_reference_coverage.csv`; (5) export as FIEBDC-3 (BC3) - BEDEC states compatibility with TCQ, Presto, Arquimedes and any BC3 program; (6) also export environmental fields if the tier includes them.
- **Export formats verified:** BC3 interoperability stated by ITeC; direct download path not verified (behind login).
- **Destination:** `data/raw/candidates/productivity/bedec/` and `data/raw/candidates/environmental/bedec/`.
- **Check first:** licence terms on redistribution and on use inside PMI.
- **Still missing without it:** Catalonia-specific rates; Spanish environmental indicators per work item.

## 2. CYPE Generador de Precios
- **Website:** https://generadordeprecios.info/obra_nueva (structures: .../Estructuras/Hormigon_armado.html; codes e.g. EHS010 pilar, EHV vigas, EHL losas; C cimentaciones; A acondicionamiento del terreno).
- **Access:** free registration ("Registrate gratis"); BC3 export requires login ("Para poder utilizar esta caracteristica ... es necesario iniciar sesion"). Legal notice (https://shop.cype.com/es/aviso-legal/): copies for personal, non-commercial use only, not transferable to third parties.
- **Steps:** (1) register; (2) select Spain > province Barcelona; (3) open each target item, set parameters (concrete class, formwork type); (4) export (BC3/XLSX/PDF per CYPE documentation); (5) store with the parameter selection recorded.
- **Destination:** `data/raw/candidates/productivity/cype/`.
- **Caution:** CYPE RC items such as EHS010 are composite (formwork + rebar + concrete per m3) - not directly comparable with BCCA's separated items. Confirm with CYPE whether research/derived use is allowed before integrating into PMI.

## 3. EC3 / Building Transparency
- **Website:** https://buildingtransparency.org/ ; API pricing/terms: https://www.buildingtransparency.org/api-access-pricing/
- **Access:** free account; API key; free tier 500 requests/day, no caching or redistribution, no commercial use. Paid order form or fee-waiver (https://www.buildingtransparency.org/wp-content/uploads/2026/05/EC3_API_Fee_Waiver_Application_fillable_final.pdf) for storage/reuse. Notify support before integrating.
- **Steps:** (1) create account; (2) request fee waiver for academic use; (3) after written permission, export Ready-Mix Concrete, Rebar, Structural steel, Plywood EPDs filtered to Spain/Europe.
- **Destination:** `data/raw/candidates/environmental/ec3/`.

## 4. BCCA Presto database (optional)
- RESOLVED 2026-11-19: inner RAR tested and extracted with 7-Zip into `data/raw/candidates/productivity/bcca_andalucia/extracted/BCCA23_V02_301023_rar/`.
- Remaining optional action: `BCCA2023_V02.Presto` is a proprietary RIB Presto database. Opening it requires a RIB Presto licence; the byte scan found no data beyond the BC3, so this is low priority.

## 5. Spanish environmental and calendar inputs not available as open data in this search
- Catalan construction labour calendar (convenio provincial de la construccion de Barcelona) - working hours/holidays must be entered by PMI user.
