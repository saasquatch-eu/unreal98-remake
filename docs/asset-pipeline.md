# Asset pipeline boundaries

Validate an actual export before selecting extraction tools or implementing a
parser. Work from a user-supplied local installation; do not download assets during
setup. Keep real exports under ignored local directories.

BSP conversion must eventually use evaluated geometry and handle subtractive
volumes, UV alignment, coordinates, scaling, collision, materials, and transforms.
Individual brush meshes must not be assumed to reconstruct the playable space.

No export route or conversion behavior has been validated. Schemas, synthetic
fixtures, and pipeline commands will be introduced in separately requested issues.
