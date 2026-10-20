"""The refusal a header formula translation raises, and the finding it becomes."""

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


class FormulaRefusal(Exception):  # noqa: N818 -- named for the finding it becomes, not an error type
    """A formula that cannot be translated; `code` is the finding it becomes."""

    def __init__(self, code: FindingCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def finding(self, entity: str, column: str, formula: str) -> Finding:
        return Finding(
            self.code,
            f"{entity}.{column}: the header formula {formula!r} {self.detail}.",
            location=Location(Section.FORM_FORMATTING, entity=entity, column=column),
        )
