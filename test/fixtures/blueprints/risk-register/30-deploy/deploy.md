# Deploying the risk register (test stand-in)

Build with:

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --time-zone Region/City \
  --site-role default \
  --out ./build
```

## Verify

- [ ] `RR_Risk` exists on the target site with the *Open risks* view as its
      default.
- [ ] `RR_` prefix was free on the target site before the paste.
