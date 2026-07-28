---
title: styles
sidebar_position: 10
---

# `dbml_sharepoint.analysis.styles`

*the fleet style standard*

The fleet style standard: semantic tokens + parameterised column styles.

Tokens resolve to SharePoint's OWN documented formatting classes (the
sp-field-severity--* set plus sanctioned Fluent UI background classes)
with the Learn reference's canonical Fluent icon pairings — never raw
hexes. Styles expand at mapping-load time into plain SP formatter JSON,
so the validator, jsgen and the deploy machinery see ordinary formatters.
Reference:
https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/column-formatting
(style guidelines; conditional formatting / data bar / trending / date
examples — the emitted structures mirror those samples).

### `StyleToken`

```python
@dataclass
class StyleToken:
    classes: str
    icon: str | None
```

StyleToken(classes: str, icon: str | None)

### `TOKENS`

```python
TOKENS = {'good': StyleToken(classes='sp-field-severity--good', icon='CheckMark'), 'low': StyleToken(classes='sp-field-severity--low', icon='Forward'), 'warning': StyleToken(classes='sp-field-severity--warning…
```

### `expand_style`

```python
def expand_style(spec: dict[str, typing.Any], context: str, theme: dict[str, dbml_sharepoint.analysis.styles.StyleToken] | None = None) -> dict[str, typing.Any]
```

Expand a declared style spec into plain SP column-formatting JSON.

### `parse_theme`

```python
def parse_theme(raw: object, context: str) -> dict[str, dbml_sharepoint.analysis.styles.StyleToken]
```

Parse the optional mapping-level style_theme key: per-token
overrides {token: {classes: [...] | str, icon: str|null}}.

