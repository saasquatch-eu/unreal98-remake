# Planned architecture

Original local installation → extraction → documented intermediate files → UE5
editor importer → assets and levels, with an independently implemented C++ runtime.

The first implemented component is the editor-independent Python T3D source
parser and inspection CLI. It retains ordered blocks, raw properties, source
lines, geometry definitions, and polygon data. The inspection report is an
inventory rather than evaluated geometry or a UE5 importer contract. Its
format is documented in `../schemas/t3d-inspection-v1.md`; tests use authored
synthetic data only.

A bounded version-61 package reader now supplies checksum-bound numeric evidence
for malformed pivot tokens. Source-space brush math and an axis-aligned synthetic
CSG occupancy reference are tested separately from source parsing. These do not
establish an evaluated castle mesh.

Automated extraction, full BSP conversion, importing, and gameplay remain future
components. Do not assume UE5 defaults reproduce UE1 behavior. Resolve source
numeric anomalies, shared definitions, and omitted class defaults before
establishing an evaluated-geometry contract.
