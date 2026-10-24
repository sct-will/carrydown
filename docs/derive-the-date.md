# Worked example: derive the date

The sample plan has people and a target, so the planning step ran in the **Fit** mode: the plan was made to fit two people and the date 2027-04-23. This page shows the other case, **Derive the date**. Suppose the same plan had people but no target. The checker then reports the end of the critical path as the derived target. The skill writes that date into `plan.yaml` as `target: {date: 2027-04-21, derived: true}`, shows it to you, and asks whether it is acceptable.

The output below was produced by running the checker on a copy of the sample's `plan.yaml` with the `target` block removed. Nothing in the sample itself was changed.

```bash
python3 scripts/check_specs.py --root sample/expense-approvals --plan plan-no-target.yaml --report
```

The report below is the whole output. Two sections differ from the run with a target. The target section says the date is derived. The earliest finish section no longer compares its date with a target. The planning review at the end is the same in both runs, because it reads how the plan is composed, not the target.

```text
Plan: Expense approvals

Schedule
  Work unit 1, Submit an expense report: 2027-02-01 to 2027-02-12 (demonstration 2027-02-12)
  Work unit 2, Route to approvers: 2027-02-15 to 2027-03-05 (demonstration 2027-03-05)
  Work unit 3, Enforce policy: 2027-03-08 to 2027-03-19 (demonstration 2027-03-19)
  Work unit 4, Pilot with one team: 2027-03-29 to 2027-04-09 (demonstration 2027-04-09)
  Work unit 5, Release: 2027-04-12 to 2027-04-23 (demonstration 2027-04-23)
  Break, Offsite and planning week: 2027-03-22 to 2027-03-26

Load (sized days of work against allocated capacity, per person and work unit)
  Capacity is the working days a person has in the work unit, minus days off, times their percent allocation.
  Person  Alloc  WU1             WU2             WU3             WU4             WU5            Total          
  tamsin  100%   3 of 10d (30%)  5 of 14d (36%)  6 of 10d (60%)  4 of 10d (40%)  0 of 10d       18 of 54d (33%)
  idris   60%    3 of 6d (50%)   4 of 9d (44%)   4 of 5d (74%)   0 of 6d         3 of 6d (50%)  14 of 32d (43%)
  No person is over 100 percent of allocated capacity in any work unit.

Critical path (longest dependency chain to the last item)
  WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11  (79 calendar days)
    WI-01 Service scaffold, flag and API contract, by 2027-02-03, tamsin
    WI-02 Report form and receipt upload, by 2027-02-10, idris
    WI-04 Approver inbox and decisions, by 2027-03-03, idris
    WI-08 Notifications and delegates, by 2027-03-17, idris
    WI-11 Release readiness and runbook, by 2027-04-21, idris

Target
  Critical path ends 2027-04-21 (derived from the critical path). There is no target in plan.yaml, so this is the derived target: the plan's end date, not a constraint.

Fit (working days each item needs, from its size and its owner's allocation, against its window)
  Every sized item fits between its last dependency and its complete_by date.

Earliest finish (forward pass over the dependencies, from sizes and allocation)
  WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11  ends 2027-03-10
    WI-01 2027-02-01 to 2027-02-03, about 3.0 working days
    WI-02 2027-02-04 to 2027-02-10, about 5.0 working days
    WI-04 2027-02-11 to 2027-02-19, about 6.7 working days
    WI-08 2027-02-22 to 2027-03-02, about 6.7 working days
    WI-11 2027-03-03 to 2027-03-10, about 5.0 working days
  Owners are not serialised in this pass. The load table above shows whether each person's work fits each work unit.

External items (outside the development plan; referenced only as external input)
  WI-05 Pilot team recruitment
  WI-10 Finance sign-off

Checkpoints
  2027-02-05  Contract freeze: WI-01
  2027-02-12  Milestone 1 demonstration: WI-02
  2027-02-26  Routing meets inbox: WI-03
  2027-03-05  Milestone 2 demonstration: WI-04
  2027-03-12  Rules meet routing: WI-06
  2027-03-19  Milestone 3 demonstration: WI-07, WI-08
  2027-04-09  Pilot readout: WI-09
  2027-04-23  Release: WI-11

Planning review (advisory, except lines marked finding; the rules are in references/planning.md)
  Milestone composition (rules 1 to 3)
    Milestone 1, Submit an expense report: Workflow (WI-01), Experience (WI-02).
      The joint check on 2027-02-12 names Workflow and Experience.
    Milestone 2, Route to approvers: Workflow (WI-03), Experience (WI-04).
      The joint check on 2027-03-05 names Workflow and Experience.
    Milestone 3, Enforce policy: Workflow (WI-06, WI-07), Experience (WI-08).
      The joint check on 2027-03-19 names Workflow and Experience.
    Milestone 4, Pilot with one team: Workflow (WI-09) only.
      One track, because: The pilot adds no screen and no notification. The Experience work it needs is support for the pilot team on the existing web client, which is not a deliverable item.
      The joint check on 2027-04-09 names Workflow and Experience.
    Milestone 5, Release: Experience (WI-11) only.
      One track, because: Release readiness is one item of rehearsal and runbook work. It sits on the Experience track because the rehearsal runs through the web client. The Workflow engineer takes part in the rehearsal and owns no new item.
      The joint check on 2027-04-23 names Workflow and Experience.
  Order of work per track (rules 4, 5 and 10)
    Workflow: WI-01, WI-03, WI-06, WI-07, WI-09. Order rationale given.
    Experience: WI-02, WI-04, WI-08, WI-11. Order rationale given.
  Theme switches (consecutive items of one owner, by date)
    tamsin: 1 switch, 0 inside a milestone.
      WI-07 (expense service) to WI-09 (export job), across milestones 3 and 4.
    idris: 2 switches, 0 inside a milestone.
      WI-04 (web client) to WI-08 (notification worker), across milestones 2 and 3.
      WI-08 (notification worker) to WI-11 (release), across milestones 3 and 5.
  Slack before checkpoints (rule 7)
    Every item completes before its checkpoint. The least slack is 2 working day(s), WI-01 before 2027-02-05.
  Critical path owners (rule 8)
    WI-01 -> WI-02 -> WI-04 -> WI-08 -> WI-11: tamsin (WI-01), idris (WI-02, WI-04, WI-08, WI-11).
  Load ratio (rule 6)
    Share of allocated capacity over the plan: tamsin 18 of 54d (33%), idris 14 of 32d (43%).
    Highest to lowest is 1.3 to 1 (idris to tamsin).
  0 finding(s).
```

A normal check of the same copy passes, because without a target there is nothing to miss:

```text
15 files clean, 0 with findings (9 work items, 5 milestones)
```

The other modes are described in [inputs.md](inputs.md#two-inputs). In **Derive the capacity** you give a target and no people, and the skill proposes a team at 100 percent as placeholder people marked `derived: true`. When you give neither, it proposes a default two-track team and a derived date and asks you to confirm.
