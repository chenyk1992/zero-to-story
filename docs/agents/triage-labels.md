# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Repo notes

- These five labels are the defaults, kept as-is. The tracker also carries the GitHub default set (`bug`, `enhancement`, `documentation`, `wontfix`, …); the two sets coexist — `wontfix` is shared by both.
- The five triage labels may not exist in the tracker yet. Create them on first use: `gh label create needs-triage --description "..." --color ...` (and likewise for `needs-info`, `ready-for-agent`, `ready-for-human`).
- `ready-for-agent` means fully specified and safe for an unattended agent — it does not grant generation or spending authority in this project. Production still requires the normal Canvas confirmation flow.
