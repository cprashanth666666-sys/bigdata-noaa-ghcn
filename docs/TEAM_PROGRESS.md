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

## Status (as of 24 Nov 2026, Checkpoint 4)

Done = Definition of Done met (notebook run-verified on Databricks; validation notebook 15: 46/46 checks, 16 Nov).
Burndown and per-member chart: [T04_CP4_Pipeline_Dashboard_Progress.docx](T04_CP4_Pipeline_Dashboard_Progress.docx) (built by `report/make_cp4_charts.py` and `report/build_cp4_report.js`).

| Owner | Points done | Points open | Complete |
|---|---|---|---|
| shwetha123920 | 17 | 0 | 100% |
| Reva-Pradeep | 13 | 0 | 100% |
| IshwaryaLaksh | 18 | 0 | 100% |
| Ashishshri10 | 6 | 10 | 38% |
| cprashanth666666-sys | 11 | 3 | 79% |
| **Team** | **65** | **13** | **83%** |

Repository access: all four teammates (Ashishshri10, IshwaryaLaksh, Reva-Pradeep, shwetha123920) have write access; no invitation pending (checked 24 Nov).

## Remaining work (proposed redistribution, confirm at stand-up)

| Task | Story | Owner | Pts | Due |
|---|---|---|---|---|
| Assemble, publish and export the four-page dashboard | 7.1 | Ashishshri10 | 5 | 24 Nov, 6 pm |
| Export notebooks as .ipynb, update README, upload T04_CP4_* files | CP4 | cprashanth666666-sys | - | 24 Nov, 6 pm |
| One-page governance note as its own file | CP4 | Reva-Pradeep | - | 24 Nov, 6 pm |
| Rerun notebook 15, pull Gold figures into the reports | 7.2 | shwetha123920 | - | 25 Nov |
| Partitioning / broadcast-join benchmark (notebook 11 or 12) | 7.3 | IshwaryaLaksh | 3 | 26 Nov |
| Final report: findings, recommendation, limits, after ratings | 7.2 | shwetha123920 | 3 | 27 Nov, 6 pm |
| Viva deck and demo script | 7.2 | Reva-Pradeep | 2 | 29 Nov |
| After-project skill ratings, learning-log entries, peer ratings | Team | Everyone | - | 25 Nov |

## How we track

1. Move the issue card on the board as work moves; close the issue only when the Definition of Done is met.
2. Branch per story off `prashbigdata`; open a PR using the template with `Closes #n`.
3. Daily async stand-up (done / doing / blocked) as a comment on your active issue.
4. Friday review and retro; update the Status table above.
