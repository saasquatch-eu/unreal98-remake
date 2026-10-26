# Planned architecture

Original local installation → extraction → documented intermediate files → UE5
editor importer → assets and levels, with an independently implemented C++ runtime.

This is a direction for later issues. There is no extraction, conversion, importer,
or gameplay implementation yet. Do not assume UE5 defaults reproduce UE1 behavior.

Keep Python content tooling independent of the UE editor. Introduce intermediate
schemas when a representative real export has been inspected, with synthetic test
fixtures kept in Git. Do not fabricate a schema or exporter contract during setup.
