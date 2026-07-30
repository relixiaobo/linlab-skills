"""Heuristic guard that blocks mutating / DDL SQL.

This is a GUARDRAIL against accidental writes, NOT a security sandbox. It is
statement-aware: it inspects the leading keyword of each `;`-separated
statement instead of substring-matching, so a read-only query with a column
named `update` or `status` is not falsely rejected, while a trailing
`...; delete from t` still is.
"""

from __future__ import annotations

import re

# Leading keywords that begin a write / DDL / session-changing statement.
_MUTATING_LEADERS = {
    "create", "alter", "drop", "insert", "update", "delete", "merge", "upsert",
    "truncate", "replace", "grant", "revoke", "call", "attach", "detach",
    "pragma", "set", "reset", "use", "load", "install", "export", "import",
    "vacuum", "copy", "checkpoint", "begin", "start", "commit", "rollback",
    "comment", "analyze",
}

# DML verbs that a leading WITH (CTE) statement can still smuggle in.
_CTE_TAIL = re.compile(r"\)\s*(insert|update|delete|merge)\b|\b(insert|update|delete|merge)\s+into\b", re.I)

_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class UnsafeSQLError(ValueError):
    """Raised when a query looks like it mutates state."""


def find_unsafe(sql: str) -> str | None:
    """Return the offending keyword if the SQL looks mutating, else None."""
    cleaned = _COMMENT_RE.sub(" ", sql)
    for statement in cleaned.split(";"):
        match = _TOKEN_RE.search(statement)
        if not match:
            continue
        lead = match.group(0).lower()
        if lead in _MUTATING_LEADERS:
            return lead
        if lead == "with":
            tail = _CTE_TAIL.search(statement[match.end():])
            if tail:
                return next(group for group in tail.groups() if group).lower()
    return None


def assert_safe(sql: str) -> None:
    """Raise UnsafeSQLError if the SQL is not a read-only query."""
    bad = find_unsafe(sql)
    if bad:
        raise UnsafeSQLError(
            f"Refusing to run mutating/DDL SQL (leading `{bad}`). Use read-only "
            "SELECT / WITH / EXPLAIN / DESCRIBE / SHOW / SUMMARIZE queries only. "
            "This is an accident guardrail, not a security sandbox."
        )
