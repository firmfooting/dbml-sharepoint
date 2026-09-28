# Risk register (test stand-in)

A blueprint written for the test suite. The wizard tests script whole runs
through a blueprint with this id, the `RR_` prefix and one list, `RR_Risk`,
whose documentation names the list so that the wizard's repointing has
something to rewrite. It is not a shipped blueprint and it is not a copy of
one.

## What it ships

One list, `RR_Risk`: a risk, its current and target rating, who owns it and
when it was last reviewed. `LevelsAboveTarget` is calculated from the two
ratings and formatted with the numeric-severity style, which is what
`test_styles.py` reads.

## Deploying

See [30-deploy/deploy.md](30-deploy/deploy.md). The deploy target is
`https://yourtenant.sharepoint.com/sites/your-site` in the time zone
`Region/City` until the wizard repoints it.
