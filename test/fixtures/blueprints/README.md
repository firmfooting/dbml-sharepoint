# Blueprints written for the suite

These directories are test data, not shipped blueprints. Nothing here is
offered by the wizard or `dbml-sharepoint blueprints` outside the test suite,
and none of them is a copy of a blueprint that ships anywhere. Each exists
because an engine test needs a whole blueprint of a particular shape and no
starter blueprint has it.

| Directory | Why it is kept |
| --- | --- |
| `risk-register/` | The wizard tests script whole runs through a blueprint with this id, its `RR_` prefix, its `Risk` list and documentation that names `RR_Risk`; `test_styles.py` reads its numeric-severity column style. A stand-in with those facts and nothing else |
| `reporting-sample/` | Two lists that read each other: reporting and demo rows in side files, a YAML merge key with an override, a lookup projection, view totals and derived columns without descriptions. The reporting sweeps need every one of those shapes |

The sweeps over the engine's output read them through `engine_blueprints()` in
`test/_paths.py`, after core's own blueprints. The sweeps over what a shipped
blueprint must satisfy read core's own blueprints only.

Edit a file here only to keep a test meaningful, and say why in the commit.
