# src/dbml_sharepoint/extract/__init__.py
"""Recover a draft schema and mapping from an existing SharePoint list.

The reverse of `build`. Fields arrive as the JSON `extract.js.txt`
downloads from a live site and become `field_xml.RawField`. `decode` turns
those into DBML types and mapping declarations; `inverse` recovers the
declarations behind an artifact by re-running the forward generator over
each candidate and keeping only what reproduces exactly; `emit` writes the
family layout, and `notes` writes down everything the read could not
recover.

This is scaffolding, not a lossless round-trip. The extraction notes are
part of the output rather than a courtesy: what the read could not recover
is the part somebody modifying the list most needs to know.
"""
