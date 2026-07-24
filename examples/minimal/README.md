# Minimal example

The smallest working input set: one table, one enum, one lookup — enough
to exercise the whole pipeline without reading anything else.

```bash
dbml-sharepoint build \
  --schema examples/minimal/schema.dbml \
  --mapping examples/minimal/mapping.yaml \
  --release examples/minimal/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

For a guided tour of the three input files and the richer feature
surface (views, formatting, permissions, demo rows), start from
[`examples/project-tracker`](../project-tracker) instead.
