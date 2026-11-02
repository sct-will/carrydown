# Confidential project fixture

This folder is a test fixture for the confidential ground truth work. It is fictional and it is not a template to copy.

It is the expense approvals sample plus one extra source.

| Source | Classification | File |
| --- | --- | --- |
| `architecture` | `repo-readers` | `ground-truth/architecture.md` |
| `company-governance` | `restricted` | `ground-truth/company-governance.md` |

The company governance policy has a section 1.5 that disagrees with the routing rule in section 3.5 of the architecture document. WI-06 cites sections 1.5 and 2.3 of the policy, so tests can check conflict notes and restricted citations.

`people.yaml` holds the fictional staffing records with an `id` for each person that matches `docs/spec/plan.yaml`. The plan still carries the older staffing fields, so the fixture passes today's checker:

```bash
python3 scripts/check_specs.py --root tests/fixtures/confidential-project --report
```

The fixture leaves out the generated engineers' skill (`docs/dev/`) and the copied checker (`tools/`).
