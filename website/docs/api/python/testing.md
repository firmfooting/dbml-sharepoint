---
title: testing
sidebar_position: 62
---

# `dbml_sharepoint.testing`

*the test kit dependents run emitted scripts with under node*

Test support for projects that execute emitted browser scripts under node.

`node.run_node` runs a script behind the SharePoint mock prelude in `sp_mock`,
and `plugin` is an opt-in pytest plugin that skips node-backed tests locally
and refuses a CI run without node. Load it from a conftest with
`pytest_plugins = ["dbml_sharepoint.testing.plugin"]`. Only `plugin` imports
pytest, which stays a test dependency rather than a runtime one.

