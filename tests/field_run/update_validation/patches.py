"""The known patches of the mechanical mode of the update validation (request-trace scenario).

They are a deterministic replay through the real update commands, not an agent's assessment. Each patch is a list
of (old text, new text) pairs on a specification or on the owner's working plan. The old text must occur exactly
once, before the section "Decisions recorded", which no patch touches. Standard library only.

The new obligation (architecture section 4.2, item 6): log lines also carry an identifier for the request or the
scheduled job run. The simulated owner settled the interface: the request identifier is the one the API gateway
assigns to each request, and a nightly job uses the scheduler's run identifier. Both are opaque strings carried in
every log line of that operation.
"""

OLD_RULE = "Log lines carry report identifiers and event types. They never carry amounts, comments or receipt contents."
NEW_RULE = ("Log lines carry report identifiers, event types and an identifier for the request or scheduled job run. "
            "They never carry amounts, comments or receipt contents.")
OPERATION = ("the operation identifier: the identifier the API gateway assigns to the request, or the scheduler's run "
             "identifier for a nightly job, an opaque string")

WI07 = "docs/spec/m3-enforce-policy/wi-07-audit-log.md"
WI08 = "docs/spec/m3-enforce-policy/wi-08-notifications-delegates.md"
WI09 = "docs/spec/m4-pilot/wi-09-ledger-export.md"
PLAN = "workspace/drafts/plan.yaml"

# item, path (as reconcile.py patch takes it), the edits
PATCHES = [
    ("WI-07", WI07, [
        ("- Log lines carry report identifiers and event types, never amounts, comments or receipt contents.",
         "- Log lines carry report identifiers, event types and " + OPERATION + ". They never carry amounts, comments or receipt contents."),
        ("6. " + OLD_RULE, "6. " + NEW_RULE),
        ("6. Add `logLine({ reportId, eventType })` to the writer and use it for the audit paths.",
         "6. Add `logLine({ reportId, eventType, operationId })` to the writer and use it for the audit paths. `operationId` is "
         + OPERATION + ". The writer refuses a log line without it."),
        ("- [ ] Log lines from a decision carry the report identifier and event type, and no amount, comment or receipt content (`tests/audit.logs.test.js`).",
         "- [ ] Log lines from a decision carry the report identifier, the event type and the identifier of the request that caused it, "
         "and no amount, comment or receipt content (`tests/audit.logs.test.js`)."),
        ("say that log lines in the worker follow the same rule (identifiers and event types only).",
         "say that log lines in the worker follow the same rule (report identifiers, event types and the request or job run identifier only)."),
    ]),
    ("WI-08", WI08, [
        ("| Ground truth | Architecture document: Sections 6.1, 6.2, 7.2 |", "| Ground truth | Architecture document: Sections 4.2, 6.1, 6.2, 7.2 |"),
        ('- GOV-2.6 (GOV-2 is the audit and retention rule). "' + OLD_RULE + '"',
         '- GOV-2.6 (GOV-2 is the audit and retention rule). "' + NEW_RULE + '"'),
        ("send it, and log only the report id and event type.",
         "send it, and log only the report id, the event type and the identifier of the request that caused the event, "
         "carried in the event from the decision."),
        ("- [ ] Captured log lines hold report ids and event types only, with no amount, comment, receipt content or address (GOV-2.6, `tests/notify-worker.test.js`).",
         "- [ ] Captured log lines hold report ids, event types and the identifier of the request that caused the event only, with no "
         "amount, comment, receipt content or address (GOV-2.6, `tests/notify-worker.test.js`)."),
        ("- architecture section 6.1, What people asked for\n",
         "- architecture section 4.2, GOV-2 Audit and retention\n- architecture section 6.1, What people asked for\n"),
    ]),
    ("WI-09", WI09, [
        ("- The file holds no personal data beyond its columns, and log lines hold no amounts (GOV-2.6).",
         "- The file holds no personal data beyond its columns, and log lines carry the scheduler's run identifier of the night's run "
         "and hold no amounts (GOV-2.6)."),
        ('- GOV-2.6. "' + OLD_RULE + '"', '- GOV-2.6. "' + NEW_RULE + '"'),
        ("Check with a fixed clock. Log only report ids and event types.",
         "Check with a fixed clock. Log only report ids, event types and the scheduler's run identifier of the run, in every log line "
         "of the run."),
        ("and captured log lines hold no amount (GOV-2.3, GOV-2.6, `tests/export-ledger-job.test.js`).",
         "and captured log lines carry the scheduler's run identifier and hold no amount (GOV-2.3, GOV-2.6, "
         "`tests/export-ledger-job.test.js`)."),
    ]),
    ("WI-08", PLAN, [
        ('        sections: "6.1, 6.2, 7.2"', '        sections: "4.2, 6.1, 6.2, 7.2"'),
    ]),
]

UNCHANGED = {
    "WI-11": "The runbook names log event types and the job, but states no log line contents. The new identifier is carried by "
             "WI-07, WI-08 and WI-09.",
    "WI-01": "The scaffold writes no log lines of an operation. Its criterion keeps personal data out of logs, which is unchanged.",
    "WI-02": "Its criterion keeps names, amounts and receipts out of log lines. The prohibition is unchanged.",
    "WI-03": "Log lines belong to WI-07 (its Out of scope). Its criterion keeps amounts and comments out, unchanged.",
    "WI-06": "Its criterion keeps amounts and comments out of refusal log lines. The prohibition is unchanged.",
}


def apply_edits(text, edits, where):
    """text with every edit applied before the section "Decisions recorded". Raises ValueError when an old text is
    not found exactly once there."""
    marker = "\n## Decisions recorded\n"
    head, sep, tail = text.partition(marker)
    for old, new in edits:
        if head.count(old) != 1:
            raise ValueError(f"the text this patch edits is not found once in {where}: {old[:70]}")
        head = head.replace(old, new)
    return head + sep + tail
