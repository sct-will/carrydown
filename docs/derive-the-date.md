# Worked example: derive the date

The sample plan has people and a target, so the planning step ran in the **Fit** mode: the plan was made to fit two people and the date 2027-04-23. This page shows the other case, **Derive the date**. Suppose the same plan had people but no target. The checker then reports the end of the critical path as the derived target. The skill writes that date into `plan.yaml` as `target: {date: 2027-04-21, derived: true}`, shows it to you, and asks whether it is acceptable.

The output below was produced by running the checker on a copy of the sample's `plan.yaml` with the `target` block removed. Nothing in the sample itself was changed.

```bash
python3 scripts/check_specs.py --root sample/expense-approvals --plan plan-no-target.yaml --report
```

The load table is unchanged, because it depends on the people and the sized work. The target section now says the date is derived.

```text
Load (sized days of work against allocated capacity, per person and work unit)
  Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.
  Person  Alloc  WU1             WU2             WU3             WU4             WU5            Total          
  tamsin  100%   3 of 10d (30%)  5 of 14d (36%)  6 of 10d (60%)  4 of 10d (40%)  0 of 10d       18 of 54d (33%)
  idris   60%    4 of 6d (67%)   4 of 9d (44%)   4 of 5d (74%)   0 of 6d         3 of 6d (50%)  15 of 32d (46%)
  No person is over 100 percent of allocated capacity in any work unit.

Critical path (longest dependency chain to the last item)
  WI-02 -> WI-04 -> WI-08 -> WI-11  (79 calendar days)
    WI-02 Report form and receipt upload, by 2027-02-10, idris
    WI-04 Approver inbox and decisions, by 2027-03-03, idris
    WI-08 Notifications and delegates, by 2027-03-18, idris
    WI-11 Release readiness and runbook, by 2027-04-21, idris

Target
  Critical path ends 2027-04-21 (derived from the critical path). There is no target in plan.yaml, so this is the derived target: the plan's end date, not a constraint.
```

A normal check of the same copy passes, because without a target there is nothing to miss:

```text
15 files clean, 0 with findings (9 work items, 5 milestones)
```

The other modes are described in [inputs.md](inputs.md#two-inputs). In **Derive the capacity** you give a target and no people, and the skill proposes a team at 100 percent as placeholder people marked `derived: true`. When you give neither, it proposes a default two-track team and a derived date and asks you to confirm.
