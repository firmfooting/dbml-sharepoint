---
title: prefix
sidebar_position: 4
---

# `dbml_sharepoint.model.prefix`

*the {prefix} placeholder and the names it expands to*

The `{prefix}` placeholder and the names it expands to.

`prefix:` names every deployed list, and a group or permission level takes
the same namespace through a placeholder at the start of its name, so one
rewrite of the prefix renames all three. The identity family reads the
prefix and the permissions family expands the names, so the expansion lives
in a public module rather than in either of them.

### `PREFIX_PLACEHOLDER`

```python
PREFIX_PLACEHOLDER = '{prefix}'
```

### `MEMBER_PLACEHOLDER`

```python
MEMBER_PLACEHOLDER = '{member}'
```

### `MEMBER_SAFE_PLACEHOLDER`

```python
MEMBER_SAFE_PLACEHOLDER = '{member_safe}'
```

### `GROUP_NAME_REFUSED_CHARACTERS`

```python
GROUP_NAME_REFUSED_CHARACTERS = frozenset({"'", '"', '*', '+', ',', '/', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '|'})
```

### `refused_group_name_characters`

```python
def refused_group_name_characters(name: str) -> tuple[str, ...]
```

The refused characters `name` carries, in the order they appear.

### `safe_member`

```python
def safe_member(member: str) -> str
```

`member` as a group name may carry it.

Each refused character becomes a space rather than being deleted, so
`A, B` reads `A B` rather than `AB`; runs of whitespace then collapse to
one. Two members can collapse onto one name, which is not special-cased
here: `duplicate_group_name` already judges the resolved names and says so.

### `prefix_stem`

```python
def prefix_stem(prefix: str) -> str
```

`RR_` names lists `RR_Risk` and groups `RR Risk Managers`: the stem.

### `expand_member`

```python
def expand_member(value: str, member: str) -> str
```

Replace every `{member}` and `{member_safe}` with the enum member.

No placement rule and no refusal for absence: where the token has to
appear is a validator's question, and a name that omits it collapses
every member onto one object rather than failing to load.

`{member_safe}` is expanded first. It would survive a naive `{member}`
pass anyway, since that token needs its closing brace, but depending on
that is depending on a spelling rather than on an order.

### `expand_prefix`

```python
def expand_prefix(value: str, prefix: str, context: str) -> str
```

Replace a leading `{prefix}` with the stem; drop it and its space when empty.

Refused anywhere but the start: the stem is a namespace and a namespace
goes first, which is also what the fleet's own naming test checks.

### `previous_object_names`

```python
def previous_object_names(raw_name: str, raw_previous: collections.abc.Sequence[str], prefix: str, previous_prefixes: collections.abc.Sequence[str], context: str) -> tuple[str, ...]
```

Every name a group or level may be found under on an unmigrated site.

Each base name (the current one and every `renamed_from`) is expanded
under the current stem and then under every previous stem; a literal base
with no placeholder is taken once. The current name is never a candidate
and nothing is listed twice.

