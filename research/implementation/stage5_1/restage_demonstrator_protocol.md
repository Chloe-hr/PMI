# RestageIFC independent demonstrator protocol

Freeze the source and sample before extraction. Use the IFC4 file
`data/raw/Restage_IP_ALL_MULTI_001.ifc` with manifest SHA-256
`9162a43f3e1041cb4825705b901edcf6d90f6d0b62f306dcaba6402184f01bb5`.
The source is the independent demonstrator in the Section A evidence manifest.

1. Use strict import with geometry enabled. Hash source bytes before and after.
   Record detected schema, wall time, class counts, diagnostics and readiness.
2. Join every fixed sample row below by exact GlobalId. Report missing or
   non-unique results without replacing the sample. Record quantity provenance,
   measurement basis, units, geometry status and missing material evidence.
3. The software gate requires a valid IFC4 import, exact source preservation,
   one extracted occurrence for each sample GlobalId, explicit geometry failure
   records, and zero planning-ready work items before engineering approval.
   Report coverage and unresolved quantities even when the software gate passes.
4. For the engineering gate, an independent reviewer measures from drawings,
   sections or independently inspected dimensions before seeing extracted
   numbers. Record the measurement rules, units, handling of voids and element
   junctions, material boundaries, reviewer, date and evidence. Obtain owner
   approval for basis-specific tolerances before comparison. Compare only like
   bases, retain all differences and report unavailable reference measurements
   explicitly. Model-authored and model-derived values share a source and can
   establish software consistency only.

| Check | Source GlobalId | Class |
| --- | --- | --- |
| QV09 | `05hYJfrx99v$KeaCnnTUNB` | IfcFooting |
| QV10 | `0DsVDPLpH6KOwWtouTiq1m` | IfcFooting |
| QV11 | `1jk_Qel3LAay24H0HaZeHK` | IfcFooting |
| QV12 | `1yKwjIZ_16yen0qjvtfq4q` | IfcFooting |
| QV13 | `0air7_zBn4rB64GHxtjcKK` | IfcWall |
| QV14 | `1JCJvyKdR8zGF7KHRmzPNI` | IfcWall |
| QV15 | `2_Awjzy5vjDQTcwWkFPSZE` | IfcWall |
| QV16 | `2u6bDe$D4AwMMhn1Na_aDi` | IfcWall |
