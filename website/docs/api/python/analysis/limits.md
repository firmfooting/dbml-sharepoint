---
title: limits
sidebar_position: 8
---

# `dbml_sharepoint.analysis.limits`

*the SharePoint ceilings, each named once*

The SharePoint ceilings this tool enforces, each named exactly once.

Every value here was previously a bare literal at two to five call sites,
several of them inside PROSE that no test ever compared against the code that
enforced it. The 1024-character validation ceiling had eight code copies and
four prose copies; the 20-index ceiling had five. Changing one meant editing a
dozen places and hoping.

That shape fails in the direction this project cares about most. A message
saying "SharePoint's limit is 1024" beside a check that now tests 2048 is not a
crash — it is a build that passes, a deploy that verifies, and an operator told
a number that is not the one being enforced. Nothing downstream can see it.

So: the number lives here, and every enforcement site and every sentence that
quotes one interpolates it. `finding_help.py` already did exactly this with
`CALCULATED_TYPE_LIST`; this module is that pattern applied to the ceilings.

**Values that coincide are still separate facts.** Four constants below are
255 and two are 5000, and they are deliberately not folded together: they are
different SharePoint surfaces that happen to share a number today. Tying a view
setting to a list-size threshold, or a field's Description bound to its
DisplayName bound, would mean a future correction to one silently moved the
other. Each constant's comment says which surface it belongs to.

Nothing in this module imports anything, so it can be read by `model/`,
`analysis/`, `analysis/checks/` and `generators/` alike without touching the
one-way dependency rule in AGENTS.md.

### `MAX_DISPLAY_TITLE`

```python
MAX_DISPLAY_TITLE = 255
```

### `MAX_INTERNAL_NAME`

```python
MAX_INTERNAL_NAME = 32
```

### `MAX_FIELD_DESCRIPTION`

```python
MAX_FIELD_DESCRIPTION = 255
```

### `MAX_GROUP_DESCRIPTION`

```python
MAX_GROUP_DESCRIPTION = 512
```

### `MAX_ROLE_DEFINITION_DESCRIPTION`

```python
MAX_ROLE_DEFINITION_DESCRIPTION = 512
```

### `MAX_TEXT_FIELD_LENGTH`

```python
MAX_TEXT_FIELD_LENGTH = 255
```

### `MAX_CALCULATED_FORMULA`

```python
MAX_CALCULATED_FORMULA = 1024
```

### `MAX_VALIDATION_FORMULA`

```python
MAX_VALIDATION_FORMULA = 1023
```

### `MAX_VALIDATION_MESSAGE`

```python
MAX_VALIDATION_MESSAGE = 1024
```

### `MAX_LIST_INDEXES`

```python
MAX_LIST_INDEXES = 20
```

### `INDEX_WARN_AT`

```python
INDEX_WARN_AT = 18
```

### `MAX_VIEW_ROW_LIMIT`

```python
MAX_VIEW_ROW_LIMIT = 5000
```

### `LIST_VIEW_THRESHOLD`

```python
LIST_VIEW_THRESHOLD = 5000
```

### `LIST_VIEW_THRESHOLD_FALLBACK_ROWS`

```python
LIST_VIEW_THRESHOLD_FALLBACK_ROWS = 1250
```

