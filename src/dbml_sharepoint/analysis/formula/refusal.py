"""The refusal a header formula translation raises, and the finding it becomes."""

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.limits import FORM_HEADER_MAX_CHARS


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


def too_large(size: int) -> FormulaRefusal:
    return FormulaRefusal(
        FindingCode.FORM_HEADER_TOO_LARGE,
        f"expands to {size} characters, more than the {FORM_HEADER_MAX_CHARS} known to save",
    )


def check_size(entity: str, column: str, expression: str) -> None:
    """Refuse a header expression longer than the largest known to save, naming the column."""
    if len(expression) > FORM_HEADER_MAX_CHARS:
        error = too_large(len(expression))
        raise FormulaRefusal(error.code, f"{entity}.{column} {error.detail}")
