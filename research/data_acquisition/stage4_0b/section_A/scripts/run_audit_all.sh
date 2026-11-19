#!/usr/bin/env bash
# Run audit_ifc.py on every local IFC (outside data/raw/candidates) in separate processes.
# Usage (repo root): bash research/data_acquisition/stage4_0b/section_A/scripts/run_audit_all.sh
OUT=data/processed/candidates/stage4_0b/section_A/ifc_audit
mkdir -p "$OUT"
LIST="$OUT/_ifc_list.txt"
find data/raw -iname "*.ifc" -not -path "data/raw/candidates/*" | sort > "$LIST"
: > "$OUT/_run_log.txt"
while IFS= read -r f; do
  id=$(printf '%s' "$f" | sha1sum | cut -c1-12)
  [ -s "$OUT/$id.json" ] && continue
  timeout 1800 .venv/Scripts/python.exe -I research/data_acquisition/stage4_0b/section_A/scripts/audit_ifc.py "$f" "$OUT/$id.json" >> "$OUT/_run_log.txt" 2>&1 || echo "FAILED $id $f (exit $?)" >> "$OUT/_run_log.txt"
done < "$LIST"
echo DONE >> "$OUT/_run_log.txt"
