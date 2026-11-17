# Team, task ownership and progress

Board: https://github.com/users/cprashanth666666-sys/projects/1
Issues: https://github.com/cprashanth666666-sys/bigdata-noaa-ghcn/issues (one per story in [PROJECT_PLAN.md](PROJECT_PLAN.md))

Board columns: Backlog -> Sprint -> In progress -> Review -> Done. Fields: Sprint, Epic, Points, Assignee.

## Owners

| GitHub profile | Scrum role | Owns | Points |
|---|---|---|---|
| [shwetha123920](https://github.com/shwetha123920) | Product Owner | E2 Spatial linking (2.1-2.3), E4 Loss definition (4.1-4.2) | 17 |
| [Reva-Pradeep](https://github.com/Reva-Pradeep) | Developer | E3 Weather features (3.1-3.3) | 13 |
| [IshwaryaLaksh](https://github.com/IshwaryaLaksh) | Developer | E5 Trigger design and basis risk (5.1-5.4) | 18 |
| [Ashishshri10](https://github.com/Ashishshri10) | Developer | E6 Pricing (6.1-6.2), 7.1 Dashboard, 7.2 Report and deck | 16 |
| [cprashanth666666-sys](https://github.com/cprashanth666666-sys) | Scrum Master | E1 Data foundation (1.1-1.4), 7.3 Benchmark | 14 |

Total: 21 stories, 78 points.

## Status (as of 17 Nov 2026)

Source: PROJECT_PLAN.md section 6; verified on Databricks 16 Nov 2026 (validation notebook 15: 46/46 checks).

| Sprint | Stories | State |
|---|---|---|
| 0-4 | 1.1-1.4, 2.1-2.3, 3.1-3.3, 4.1-4.2, 5.1-5.3 | Done |
| 5 | 5.4, 6.1, 6.2 done; 7.1 dashboard in progress | In progress |
| 6 | 7.2 report and deck, 7.3 benchmark | Backlog |

## How we track

1. Move the issue card on the board as work moves; close the issue only when the Definition of Done is met.
2. Branch per story off `prashbigdata`; open a PR using the template with `Closes #n`.
3. Daily async stand-up (done / doing / blocked) as a comment on your active issue.
4. Friday review and retro; update the Status table above.
