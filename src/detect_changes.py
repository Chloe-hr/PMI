
from pathlib import Path
import csv
import ifcopenshell

ROOT = Path(__file__).resolve().parents[1]

V1_PATH = ROOT / "data" / "raw" / "model_v1.ifc"
V2_PATH = ROOT / "data" / "raw" / "model_v2.ifc"
OUTPUT_PATH = ROOT / "data" / "processed" / "changes.csv"

def get_elements(model):
    return {
        e.GlobalId: e
        for e in model.by_type("IfcBuildingElement")
        if e.GlobalId
    }

def main():
    v1 = ifcopenshell.open(str(V1_PATH))
    v2 = ifcopenshell.open(str(V2_PATH))

    old_elements = get_elements(v1)
    new_elements = get_elements(v2)

    rows = []

    for guid in sorted(old_elements.keys() | new_elements.keys()):
        old = old_elements.get(guid)
        new = new_elements.get(guid)

        if old is None:
            status = "ADDED"
        elif new is None:
            status = "DELETED"
        elif (
            old.Name != new.Name
            or old.Description != new.Description
        ):
            status = "MODIFIED"
        else:
            status = "UNCHANGED"

        element = new if new is not None else old

        rows.append({
            "global_id": guid,
            "ifc_type": element.is_a(),
            "name": element.Name or "",
            "status": status,
            "old_name": old.Name or "" if old is not None else "",
            "new_name": new.Name or "" if new is not None else "",
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "global_id",
                "ifc_type",
                "name",
                "status",
                "old_name",
                "new_name",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("Change report saved:", OUTPUT_PATH)

    for status in ("ADDED", "DELETED", "MODIFIED", "UNCHANGED"):
        count = sum(row["status"] == status for row in rows)
        print(f"{status}: {count}")

if __name__ == "__main__":
    main()

