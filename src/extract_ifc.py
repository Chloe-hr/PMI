import csv
from pathlib import Path

import ifcopenshell


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "data" / "raw" / "model_v1.ifc"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "elements.csv"


def main():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"IFC file not found: {MODEL_PATH}")

    model = ifcopenshell.open(str(MODEL_PATH))
    elements = model.by_type("IfcBuildingElement")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["global_id", "ifc_type", "name", "source_model"],
        )
        writer.writeheader()

        for element in elements:
            writer.writerow({
                "global_id": element.GlobalId,
                "ifc_type": element.is_a(),
                "name": element.Name or "",
                "source_model": MODEL_PATH.name,
            })

    print(f"Number of building elements: {len(elements)}")
    print(f"CSV saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()