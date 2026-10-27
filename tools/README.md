# Python source inspection

Use the repository-local Python environment. The tool has no UE editor dependency
and does not install or call an exporter, change a map, or generate UE5 content.

```sh
.venv/bin/python -m ue1_converter inspect-t3d \
  data/local/Unreal/Maps/Unreal/Unreal.t3d \
  --output data/converted/Unreal/Maps/Unreal/Unreal.inspection.json
bash scripts/run-tests.sh
```

Output directories must already exist. Existing reports require `--force` to
replace. Omitting `--output` prints JSON; its contents still belong in private
storage. The default text codec is UTF-8; use `--encoding` explicitly for another
known export encoding. Decoding errors are never silently replaced.

Success exits 0 even when the report contains source warnings. Invalid structure,
unsupported geometry records, malformed polygon vectors, decoding failures, and
file errors exit 2. Source warnings must be resolved before conversion. The CLI
rejects writing over its input, including an existing symlink or hardlink alias.

`ue1_converter.t3d.parse_t3d(text)` returns a document with the complete source
text and ordered blocks, header attributes, and raw actor property assignments.
Source lines are one-based. `read_polygon(block)` reads vertices and texture
basis/pan data without changing winding, coordinates, or mapping units. Header
flags, link values, and resource spelling remain available on the polygon block.
`parse_struct` reads specified fields without supplying omitted defaults.

The supported export subset is Map → Actor → Brush → PolyList → Polygon, with
single-line properties. Unknown actor properties are retained. Unsupported block
types and unknown polygon records produce errors rather than being discarded.
This is not a parser for arbitrary UE1/UE5 text objects. It does not round-trip
edited exports, apply transforms, repair malformed numbers, resolve class defaults,
evaluate CSG, triangulate, or reconstruct camera behavior.

`inspection.inspect_document` produces the inventory described in
`../schemas/t3d-inspection-v1.md`. Real-map reports stay under ignored
`data/converted/`; only manually authored synthetic fixtures belong in tests.
The reserved extract/convert/validate directories remain unused.
