"""The measured formula facts the reference evaluator is pinned to.

Printed by test/manual/formula-facts-probe.js. Dates in
`instant` form are UTC instants of site-local midnight; `displayed` is the site-local date as
the item text shows it (day/month/year).
"""

BLANK_OPERANDS = {"number": 5, "text": "abc", "date": "2026-03-15T00:00:00Z", "choice": "Low"}

# Operator -> (sign, {operand type: {blank side: the cell the calculated column gave}}).
# "left" is a blank on the left of the sign, "right" a blank on the right, "both" two blanks.
BLANK_COERCION = {
    "add": (
        "+",
        {
            "number": {"left": "5.00000000000000", "right": "5.00000000000000", "both": "0"},
            "text": {"left": "error;#1", "right": "error;#1", "both": "0"},
            "date": {"left": "46096.4583333333", "right": "46096.4583333333", "both": "0"},
            "choice": {"left": "error;#1", "right": "error;#1", "both": "0"},
        },
    ),
    "sub": (
        "-",
        {
            "number": {"left": "-5.00000000000000", "right": "5.00000000000000", "both": "0"},
            "text": {"left": "error;#1", "right": "error;#1", "both": "0"},
            "date": {"left": "-46096.4583333333", "right": "46096.4583333333", "both": "0"},
            "choice": {"left": "error;#1", "right": "error;#1", "both": "0"},
        },
    ),
    "mul": (
        "*",
        {
            "number": {"left": "0", "right": "0", "both": "0"},
            "text": {"left": "error;#1", "right": "error;#1", "both": "0"},
            "date": {"left": "0", "right": "0", "both": "0"},
            "choice": {"left": "error;#1", "right": "error;#1", "both": "0"},
        },
    ),
    "div": (
        "/",
        {
            "number": {"left": "0", "right": "error;#0", "both": "error;#0"},
            "text": {"left": "error;#1", "right": "error;#1", "both": "error;#0"},
            "date": {"left": "0", "right": "error;#0", "both": "error;#0"},
            "choice": {"left": "error;#1", "right": "error;#1", "both": "error;#0"},
        },
    ),
    "pow": (
        "^",
        {
            "number": {"left": "0", "right": "1.00000000000000", "both": "error;#5"},
            "text": {"left": "error;#1", "right": "error;#1", "both": "error;#5"},
            "date": {"left": "0", "right": "1.00000000000000", "both": "error;#5"},
            "choice": {"left": "error;#1", "right": "error;#1", "both": "error;#5"},
        },
    ),
    "cat": (
        "&",
        {
            "number": {"left": "5", "right": "5", "both": ""},
            "text": {"left": "abc", "right": "abc", "both": ""},
            "date": {"left": "46096.4583333333", "right": "46096.4583333333", "both": ""},
            "choice": {"left": "Low", "right": "Low", "both": ""},
        },
    ),
    "eq": (
        "=",
        {
            "number": {"left": "F", "right": "F", "both": "T"},
            "text": {"left": "F", "right": "F", "both": "T"},
            "date": {"left": "F", "right": "F", "both": "T"},
            "choice": {"left": "F", "right": "F", "both": "T"},
        },
    ),
    "ne": (
        "<>",
        {
            "number": {"left": "T", "right": "T", "both": "F"},
            "text": {"left": "T", "right": "T", "both": "F"},
            "date": {"left": "T", "right": "T", "both": "F"},
            "choice": {"left": "T", "right": "T", "both": "F"},
        },
    ),
    "lt": (
        "<",
        {
            "number": {"left": "T", "right": "F", "both": "F"},
            "text": {"left": "T", "right": "F", "both": "F"},
            "date": {"left": "T", "right": "F", "both": "F"},
            "choice": {"left": "T", "right": "F", "both": "F"},
        },
    ),
    "gt": (
        ">",
        {
            "number": {"left": "F", "right": "T", "both": "F"},
            "text": {"left": "F", "right": "T", "both": "F"},
            "date": {"left": "F", "right": "T", "both": "F"},
            "choice": {"left": "F", "right": "T", "both": "F"},
        },
    ),
    "le": (
        "<=",
        {
            "number": {"left": "T", "right": "F", "both": "T"},
            "text": {"left": "T", "right": "F", "both": "T"},
            "date": {"left": "T", "right": "F", "both": "T"},
            "choice": {"left": "T", "right": "F", "both": "T"},
        },
    ),
    "ge": (
        ">=",
        {
            "number": {"left": "F", "right": "T", "both": "T"},
            "text": {"left": "F", "right": "T", "both": "T"},
            "date": {"left": "F", "right": "T", "both": "T"},
            "choice": {"left": "F", "right": "T", "both": "T"},
        },
    ),
}

DATE_OVERFLOW = {
    "DATE(2026,13,5)": {"instant": "2027-01-04T13:00:00Z", "displayed": "5/01/2027"},
    "DATE(2026,1,0)": {"instant": "2025-12-30T13:00:00Z", "displayed": "31/12/2025"},
    "DATE(2026,2,31)": {"instant": "2026-03-02T13:00:00Z", "displayed": "3/03/2026"},
    "DATE(2024,2,29)": {"instant": "2024-02-28T13:00:00Z", "displayed": "29/02/2024"},
    "DATE(YEAR([DateLeap])+1,MONTH([DateLeap]),DAY([DateLeap]))": {
        "instant": "2025-02-28T13:00:00Z",
        "displayed": "1/03/2025",
    },
}

TEXT_EQUALITY_CASE = {"literal": "T", "column": "T"}

CREATED_PLUS_DAYS_DAY = {
    "created": "2026-06-10T14:20:48Z",
    "utc_day": "2026-06-10",
    "standard_local_day": "2026-06-11",
    "daylight_local_day": "2026-06-11",
    "plus_zero": "2026-06-10T14:20:48Z",
    "plus_one": "2026-06-11T14:20:48Z",
    "shown_zero": "2026-06-11",
    "shown_one": "2026-06-12",
    "verdict": "SITE-LOCAL DAY",
}

CALCULATED_DATE_READ = {
    "Cdr": {"rest": "2026-03-14T13:00:00Z", "text": "15/03/2026"},
    "CdrTime": {"rest": "2026-06-10T14:20:48Z", "text": "11/06/2026 12:20 AM"},
    "created_text": "11/06/2026 12:20 AM",
}

CALCULATED_NUMBER_DISPLAY = {
    "Ndisp": {"rest": "1.66666666666667", "text": "1.66666666666667"},
    "NdispWhole": {"rest": "10.0000000000000", "text": "10"},
    "decimals_attribute": "absent",
}

HEADER_SIZE_LIMIT = {"largest_saved": 1048576, "first_refused": None, "refusal": "", "cap": 1048576}

# Measured: Number([$D]) of a date field is its epoch milliseconds, the instant as stored.
DATE_FIELD_EPOCH_MS = {
    "date only": {
        "2026-07-15T00:00:00Z": 1784073600000,
        "2026-10-04T00:00:00Z": 1791072000000,
        "2026-10-21T13:30:00Z": 1792589400000,
        "2026-10-20T13:00:00Z": 1792501200000,
    },
    "date and time": {
        "2026-07-14T14:30:00Z": 1784039400000,
        "2026-10-03T14:30:00Z": 1791037800000,
        "2026-10-04T12:30:00Z": 1791117000000,
    },
}

# Measured: a date-only column keeps the instant written and shows the site's day of it.
DATE_ONLY_STORED_AS_WRITTEN = {
    "2026-10-21T13:30:00Z": {"read_back": "2026-10-21T13:30:00Z", "displayed": "22/10/2026"},
    "2026-10-21T00:00:00+11:00": {"read_back": "2026-10-20T13:00:00Z", "displayed": "21/10/2026"},
}

# Measured: a blank date field.
BLANK_DATE_FIELD = {"Number": 0, "toString": "", "equals_empty_text": False, "Date_is_epoch": True}

# Measured with the browser in the site's own zone: the browser-zone parts of the date-only value
# 2026-10-04 (getMonth counts from 0).
BROWSER_PARTS_OF_DATE_ONLY = {
    "browser": "Australia/Melbourne",
    "value": "2026-10-04T00:00:00Z",
    "getDate": 4,
    "getMonth": 9,
    "getYear": 2026,
}
