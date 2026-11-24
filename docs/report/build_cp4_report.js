// Builds docs/T04_CP4_Pipeline_Dashboard_Progress.docx: Checkpoint 4 project file, Team No. 4.
// Run from docs/report:  NODE_PATH="$(npm root -g)" node build_cp4_report.js   (charts first: python make_cp4_charts.py)
// XIME house style: A4, 1" margins, Times New Roman 12 pt, 1.5 spacing, page border, unnumbered cover.
// Sources: PROJECT_PLAN.md, TEAM_PROGRESS.md, git history, GitHub API (profiles, collaborators, issues,
// project board) read on 24 Nov 2026. Gold-table figures come from docs/report/results_24nov.md (queried 24 Nov 2026).

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, PageBreak, Footer, ImageRun, LevelFormat, PageNumber, LineRuleType,
  BorderStyle, PageBorderDisplay, PageBorderOffsetFrom, ExternalHyperlink,
} = require("docx");
const fs = require("fs");
const path = require("path");

const FONT = "Times New Roman";
const GREY = "595959";
const OUT = path.join(__dirname, "..", process.env.OUT_NAME || "T04_CP4_Pipeline_Dashboard_Report.docx");
const SAFE = 8950; // A4 printable width 9026 twips, minus a buffer
const TODO = /\[TO FILL[^\]]*\]/;
const SPLIT = /(\[TO FILL[^\]]*\])/;
const BODY = { after: 140, line: 360, lineRule: LineRuleType.AUTO };
const REPO = "https://github.com/cprashanth666666-sys/bigdata-noaa-ghcn";
const BOARD = "https://github.com/users/cprashanth666666-sys/projects/1";

// ---------- helpers ----------
const runs = (text, opts = {}) => text.split(SPLIT).filter(Boolean).map((t) =>
  new TextRun({ text: t, font: FONT, size: 24, ...opts, ...(TODO.test(t) ? { highlight: "yellow" } : {}) }));
const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true,
  children: [new TextRun({ text: t, bold: true, size: 28, font: FONT, color: "000000" })],
  spacing: { before: 280, after: 120, line: 300, lineRule: LineRuleType.AUTO } });
const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true,
  children: [new TextRun({ text: t, bold: true, size: 24, font: FONT, color: "000000" })],
  spacing: { before: 160, after: 80, line: 300, lineRule: LineRuleType.AUTO } });
const p = (t) => new Paragraph({ children: runs(t), alignment: AlignmentType.JUSTIFIED, spacing: BODY });
const pc = (children) => new Paragraph({ children, alignment: AlignmentType.JUSTIFIED, spacing: BODY });
const bullet = (t) => new Paragraph({ children: runs(t), numbering: { reference: "bullets", level: 0 },
  alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 320, lineRule: LineRuleType.AUTO } });
const link = (text, url, size = 24) => new ExternalHyperlink({ link: url,
  children: [new TextRun({ text, font: FONT, size, style: "Hyperlink" })] });

// Cell content: a string (one Paragraph per "\n" line) or an array of runs/hyperlinks for one line.
function cell(content, { header = false, width, shade } = {}) {
  const paras = Array.isArray(content)
    ? [new Paragraph({ spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO }, children: content })]
    : String(content).split("\n").map((line) => new Paragraph({
      spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO },
      children: line.split(SPLIT).filter(Boolean).map((t) => new TextRun({
        text: t, bold: header, size: 19, font: FONT, color: header ? "FFFFFF" : "000000",
        ...(TODO.test(t) ? { highlight: "yellow" } : {}) })),
    }));
  return new TableCell({ width: { size: width, type: WidthType.DXA }, children: paras,
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 } });
}
const widthLog = [];
function table(label, headers, rows, widths) {
  const sum = widths.reduce((a, b) => a + b, 0);
  if (sum > SAFE) throw new Error(`${label}: widths sum ${sum} > ${SAFE}`);
  rows.forEach((r, i) => { if (r.length !== widths.length) throw new Error(`${label}: row ${i} has ${r.length} cells`); });
  widthLog.push(`${label}=${sum}`);
  return new Table({ columnWidths: widths, width: { size: sum, type: WidthType.DXA }, rows: [
    new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, { header: true, width: widths[i], shade: "000000" })) }),
    ...rows.map((r, k) => new TableRow({ cantSplit: true,
      children: r.map((c, i) => cell(c, { width: widths[i], shade: k % 2 ? "F2F2F2" : "FFFFFF" })) })),
  ] });
}
let tableNo = 0, figureNo = 0;
const tableCaption = (t) => { tableNo += 1; return new Paragraph({ keepNext: true, spacing: { before: 160, after: 60 },
  children: [new TextRun({ text: `Table ${tableNo}. ${t}`, bold: true, size: 20, font: FONT })] }); };
const figureCaption = (t) => { figureNo += 1; return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: `Figure ${figureNo}. ${t}`, bold: true, size: 20, font: FONT })] }); };
const source = (t) => new Paragraph({ alignment: AlignmentType.JUSTIFIED,
  spacing: { after: 160, line: 260, lineRule: LineRuleType.AUTO },
  children: t.split(SPLIT).filter(Boolean).map((x) => new TextRun({ text: x, size: 18, italics: true, color: GREY, font: FONT,
    ...(TODO.test(x) ? { highlight: "yellow" } : {}) })) });
function image(file, widthPx) {
  const b = fs.readFileSync(file);
  const w = b.readUInt32BE(16), h = b.readUInt32BE(20);
  return new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 80, after: 40 },
    children: [new ImageRun({ data: b, transformation: { width: widthPx, height: Math.round(widthPx * h / w) }, type: "png" })] });
}
const centre = (t, opts = {}, spacing = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing,
  children: [new TextRun({ text: t, font: FONT, size: 24, ...opts })] });
const gh = (login) => [link(login, `https://github.com/${login}`, 19)];
const T = (t) => new TextRun({ text: t, font: FONT, size: 19 });

// ---------- cover ----------
const cover = [
  new Paragraph({ spacing: { before: 300 }, children: [] }),
  centre("A Project Report on", { size: 26 }, { after: 240 }),
  centre("“Parametric Weather Insurance for US Crop Risk: Quantifying Basis Risk with Big Data on Databricks”",
    { size: 30, bold: true, italics: true }, { after: 200, line: 360, lineRule: LineRuleType.AUTO }),
  centre("Checkpoint 4: Pipeline, Dashboard and AI/ML Model", { size: 26, bold: true }, { after: 60 }),
  centre("Build audit, team progress, burndown and work plan to submission", { size: 22, italics: true }, { after: 240 }),
  centre("Team No. 4", { size: 26, bold: true }, { after: 240 }),
  centre("Submitted to", { size: 24 }, { after: 60 }),
  centre("Xavier Institute of Management & Entrepreneurship, Bangalore", { size: 26, bold: true }, { after: 240 }),
  centre("Submitted in partial fulfilment of the Big Data Project Work requirement, Business Analytics (PGDM)",
    { size: 22, italics: true }, { after: 200, line: 300, lineRule: LineRuleType.AUTO }),
  centre("Under the guidance of", { size: 22, italics: true }, { after: 80 }),
  centre("Nikhil D Johnathan", { size: 26, bold: true }, { after: 40 }),
  centre("Course instructor, XIME", { size: 22, italics: true }, { after: 200 }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "Repository: ", font: FONT, size: 22 }), link("github.com/cprashanth666666-sys/bigdata-noaa-ghcn", REPO, 22)] }),
  centre("24 November 2026", { size: 22 }, { after: 240 }),
  new Table({ alignment: AlignmentType.CENTER, columnWidths: [1500, 3300, 2600], width: { size: 7400, type: WidthType.DXA },
    rows: [["Roll No.", "Name", "GitHub"], ["BA05010", "Ashish Kumar Shrivastava", "Ashishshri10"], ["BA05015", "C. Prashanth", "cprashanth666666-sys"],
      ["BA05023", "Ishwarya Lakshmi V", "IshwaryaLaksh"], ["BA05047", "Reva Pradeep", "Reva-Pradeep"], ["BA05054", "Shwetha Shyam Mathew", "shwetha123920"]]
      .map((r, i) => new TableRow({ children: r.map((c, j) => cell(i > 0 && j === 2 ? gh(c) : c,
        { header: i === 0, width: [1500, 3300, 2600][j], shade: i === 0 ? "000000" : undefined })) })) }),
  new Paragraph({ spacing: { before: 300 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ data: fs.readFileSync(path.join(__dirname, "xime_logo.png")),
    transformation: { width: 300, height: Math.round(300 / 3.386) }, type: "png" })] }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- 1. CP4 deliverables ----------
const s1 = [
  h1("1. Checkpoint 4 Deliverables and Their Status"),
  p("The Student Guide defines Checkpoint 4 (due 24 November, 6 pm, 5 marks) as a finished pipeline with gold tables and a dashboard, a README, and a one-page data governance note, with notebooks submitted as exported .ipynb files. Table 1 checks each item against what is actually in the repository and on Databricks today."),
  tableCaption("Checkpoint 4 deliverables against the evidence"),
  table("T1", ["Deliverable (Student Guide)", "Status on 24 Nov", "Evidence", "Owner"], [
    ["Finished pipeline with gold tables", "Done", "Notebooks 00 to 15; run as Databricks jobs on 16 Nov; validation notebook 15 passed 46 of 46 checks (table pipeline_validation)", "All (see Table 2)"],
    ["Analytics model and evaluation metrics", "Done", "Trigger model scored as a classifier (hit, miss, false alarm) in notebook 11; premium model in 13. Results: Section 3", "IshwaryaLaksh, Ashishshri10"],
    ["Dashboard", "Done", "Four-page AI/BI dashboard published on 24 Nov from the eight v_* views (notebook 14): basis-risk and coverage maps, trigger comparison, premium map and distribution, worst-year counters. Built from code (databricks/dashboard/build_dashboard.py); definition committed as parametric_insurance.lvdash.json", "Ashishshri10"],
    ["README", "Done", "README.md lists both datasets, all notebooks with their outputs and run order, the India pilot, and links to this report, the results file and the dashboard guide", "cprashanth666666-sys"],
    ["One-page governance note", "Drafted", "Section 6 of this file (licence, privacy, bias, data quality)", "Reva-Pradeep"],
    ["Notebooks as .ipynb", "Done", "All 23 notebooks (00–15 US pipeline, 16–22 India pilot) exported from the Databricks workspace to notebooks_ipynb/; each export checked line by line against the repository source", "cprashanth666666-sys"],
  ], [2000, 1350, 4050, 1500]),
  source("Sources: Big Data Project Work Student Guide (20 Oct 2026), checkpoint table; repository main branch at commit 8a294d3; docs/PROJECT_PLAN.md section 6."),
];

// ---------- 2. build audit ----------
const S = [
  ["1.1", "GHCN-Daily in Delta", "01", 3, "cprashanth666666-sys"], ["1.2", "Yields and county centroids", "02", 3, "cprashanth666666-sys"],
  ["1.3", "Weather back to 2000", "03", 3, "cprashanth666666-sys"], ["1.4", "Data-quality report", "04", 2, "cprashanth666666-sys"],
  ["2.1", "County to nearest stations", "05", 5, "shwetha123920"], ["2.2", "Usable stations only", "06", 3, "shwetha123920"],
  ["2.3", "Counties lacking a station", "07", 2, "shwetha123920"], ["3.1", "Growing-season rainfall", "08", 5, "Reva-Pradeep"],
  ["3.2", "Heat-stress days", "08", 3, "Reva-Pradeep"], ["3.3", "Dry-spell length", "09", 5, "Reva-Pradeep"],
  ["4.1", "Detrended yields", "10", 5, "shwetha123920"], ["4.2", "Loss event (< 85% of trend)", "10", 2, "shwetha123920"],
  ["5.1", "Triggers vs losses", "11", 5, "IshwaryaLaksh"], ["5.2", "Basis risk quantified", "11", 5, "IshwaryaLaksh"],
  ["5.3", "Best trigger per region", "11", 3, "IshwaryaLaksh"], ["5.4", "Distance and basis risk", "12", 5, "IshwaryaLaksh"],
  ["6.1", "Burn-cost premium", "13", 3, "Ashishshri10"], ["6.2", "Portfolio view", "13", 3, "Ashishshri10"],
];
const s2 = [
  h1("2. Build Audit: Is Everything Built Where the Tracker Says?"),
  p("Each story in the project plan was traced to its notebook in the repository, its GitHub issue and its Databricks run. Table 2 lists the result. All 18 stories the tracker marks done have a committed notebook, a closed issue and a passing check in notebook 15. The three open stories are exactly the ones the tracker marks open, so the tracker is accurate."),
  tableCaption("Story-by-story build audit (21 stories, 78 points)"),
  table("T2", ["ID", "Story", "Notebook", "Pts", "Owner", "Issue", "Run-verified"], [
    ...S.map(([id, st, nb, pts, own]) => [id, st, nb, String(pts), gh(own), "Closed", "Yes, 16 Nov"]),
    ["7.1", "Dashboard", "14 + dashboard/", "5", gh("Ashishshri10"), "Closed", "Yes, 24 Nov"],
    ["7.2", "Report and viva deck", "docs/", "5", gh("Ashishshri10"), "Open", "Draft with placeholders"],
    ["7.3", "Big-data benchmark", "none yet", "3", gh("cprashanth666666-sys"), "Open", "Not started"],
  ], [520, 2350, 900, 480, 2050, 750, 1850]),
  source("Sources: docs/PROJECT_PLAN.md sections 5 and 6; GitHub issues #1 to #21 and project board “DE & BDA - Parametric Weather Insurance” (read 24 Nov 2026); Databricks job runs 39815730124059 and 995256526456964."),
  h2("Gaps the audit found"),
  bullet("Dashboard (7.1): the audit found the eight views built but no dashboard. It was then generated from code and published the same day; its counters were checked against portfolio_summary (corn: expected payout USD 8,014.53, worst year 2012, loss ratio 2.7)."),
  bullet("Findings: the final-report draft of 16 November had blank result cells, written before notebooks 06 to 14 ran. They were filled on 24 November from the Gold tables and checked a second way (Table 4)."),
  bullet("GitHub attribution: all 14 commits on main come from one account (cprashanth666666-sys) and no pull requests exist, so the history does not show who built what. Issues #1 to #21 have no assignee; ownership is recorded only in docs/TEAM_PROGRESS.md."),
  bullet("Repository access: all four teammates (Ashishshri10, IshwaryaLaksh, Reva-Pradeep, shwetha123920) have write access; Reva-Pradeep’s invitation of 17 November was accepted by 24 November, and none is pending."),
  bullet("Branches: main holds one commit (8a294d3, team tracking) that the integration branch prashbigdata does not, the reverse of the convention in the plan."),
  bullet("Roles: the Student Guide asks for the roles Data Wrangler, Analyst, Storyteller, Governance Guardian and Project Captain, swapped after Checkpoint 3. The tracker uses Scrum roles only, so the swap is not recorded."),
];

// ---------- 3. pipeline, model, metrics, dashboard ----------
const s3 = [
  h1("3. Medallion Pipeline, Analytics Model and Evaluation Metrics"),
  p("Figure 1 shows the pipeline. Bronze holds the raw NOAA weather (263.4 million rows for 2019 to 2025, extended back to 2000 for US stations), the USDA NASS crops file (23.9 million rows) and the Census county gazetteer. Silver keeps station-years with at least 90% of growing-season days observed and links each county to its nearest usable station within 30 km. Gold holds county-year weather indices, detrended yields with a loss flag, trigger scores and premiums."),
  image(path.join(__dirname, "fig1_pipeline.png"), 560),
  figureCaption("Business problem, data and medallion pipeline"),
  source("Source: notebooks 00 to 15 in the databricks/ folder of the repository."),
  h2("The model"),
  p("The analytics model is a parametric trigger: for each county, crop and weather index, it pays in a year when the index is among the worst share of that county’s years (payout frequency 10%, 15%, 20%, 25% or 30%). Five indices are tested: season rainfall, driest 30-day rainfall, days above 30 °C, days above 35 °C and longest dry spell. The model is scored like a binary classifier against the observed loss label (yield below 85% of the county’s own linear trend)."),
  tableCaption("Evaluation metrics used for the trigger and pricing models"),
  table("T3", ["Metric", "Definition", "Business meaning", "Table (notebook)"], [
    ["Hit rate (recall)", "Hits ÷ loss years", "Share of real losses the policy pays", "trigger_eval_county (11)"],
    ["Miss rate = basis risk", "Loss years with no payout ÷ loss years (1 − recall)", "Farmer lost a crop and was not paid", "trigger_eval_county, trigger_eval_dist_band (11)"],
    ["False-alarm rate", "Payouts in non-loss years ÷ non-loss years", "Insurer pays with no loss; raises the premium", "trigger_eval_county (11)"],
    ["Selection rule", "Lowest pooled miss rate with false-alarm rate ≤ 25% and ≥ 10 loss years, per state and crop", "One trigger to sell per region", "best_trigger_region (11)"],
    ["Distance decay", "Median station-pair correlation by distance bin", "Why far stations miss losses", "corr_distance_curve (12)"],
    ["Burn-cost premium", "Average historic payout ÷ sum insured × (1 + 25% loading)", "Price of cover per acre", "premium_county (13)"],
    ["Worst-year loss ratio", "Worst-year payout ÷ annual premium", "Capital the insurer must hold", "portfolio_summary (13)"],
  ], [1700, 2900, 2300, 2000]),
  source("Source: header comments of notebooks 11, 12 and 13 (FA_CAP = 0.25, MIN_REGION_LOSSES = 10, COVERAGE = 0.85, PAYOUT_SHARE = 0.25, LOADING = 0.25; crop prices USD 4.50 corn and USD 11.00 soybeans are illustrative, not market quotes)."),
  tableCaption("Results by research question"),
  table("T4", ["Question", "Result", "Source table"], [
    ["Share of loss years", "Corn 9.1% of 10,768 county-years (977 losses, 445 counties); soybeans 10.4% of 10,420 (1,078). 2012 drought: 65% of corn and 42% of soybean county-years were losses", "county_yield_trend"],
    ["RQ1: best trigger per state and crop", "Heat-day triggers win in Illinois, Indiana and Iowa for both crops; rainfall triggers win in Minnesota and Nebraska. Miss rate 10.9% (Indiana corn) to 54.8% (Minnesota corn), against 69% to 74% for a trigger that paid at random", "best_trigger_region"],
    ["RQ2: basis risk and distance", "Corn, days > 35 °C: miss rate flat at 32% to 33% across 0–30 km. Season rainfall: 53%, 51%, then 64% at 20–30 km. Rainfall correlation between stations falls from 0.91 to 0.80 within 40 km; heat stays near 0.89", "trigger_eval_dist_band; corr_distance_curve"],
    ["RQ3: premium", "Median premium rate 8.5% (corn) and 9.1% (soybeans); USD 62 and 49 per acre. Long-run loss ratio 0.79. Worst year 2012: payouts 2.7 times one year’s premium for corn", "premium_county; portfolio_summary"],
    ["RQ4: coverage gaps", "Of 470 Corn Belt counties, 87 never had a usable station within 30 km and 155 were covered in under half of the years. Median distance to the nearest usable station: 7.4 km", "county_coverage_gaps"],
    ["Pipeline validation", "46 of 46 checks passed (16 Nov 2026)", "pipeline_validation"],
  ], [2000, 5000, 1900]),
  source("Source: Gold tables in workspace.default, queried 24 Nov 2026 on the Databricks SQL warehouse. Each headline figure was re-derived a second way (for example, loss counts from yield_value < 0.85 × trend_yield; the Iowa corn miss rate pooled from trigger_eval_county). Queries and checks: docs/report/results_24nov.md."),
  image(path.join(__dirname, "fig2_distance.png"), 580),
  figureCaption("Basis risk and weather similarity by distance"),
  source("Source: trigger_eval_dist_band (corn, trigger pays in 20% of years) and corr_distance_curve. The 20–30 km band holds only 36 corn loss years, so its rate is less certain."),
  h2("Recommendation"),
  p("Because the data shows that heat-day triggers miss about one loss in three and do not get worse with distance, while rainfall triggers miss about half of losses and degrade beyond 20 km, we recommend that the insurer sell heat-day triggers in Illinois, Indiana and Iowa and offer rainfall cover in Minnesota and Nebraska only where a usable station is within 20 km, with the limit that thresholds were fitted on the same years they were tested on, so real miss rates will be higher."),
  h2("Dashboard"),
  p("The dashboard has four pages, each answering one question an insurer would ask: where the trigger fails farmers (basis-risk map, counties without a station), which trigger works and why distance matters (miss rate by index and by distance band, correlation decay), what cover costs (premium map and table), and how bad a year can get (expected payout, worst year, worst-year loss ratio). It reads only the views from notebook 14, so its numbers are the same as the Gold tables."),
];

// ---------- 4. team and progress ----------
const s4 = [
  h1("4. Team, GitHub Profiles and Progress So Far"),
  p("All five members’ GitHub profiles were looked up through the GitHub API on 24 November 2026. Each one exists, and each is listed in docs/TEAM_PROGRESS.md and on the cover of this file. Table 5 links each profile and shows its access to the repository."),
  tableCaption("Team members and their GitHub profiles"),
  table("T5", ["Roll No.", "Name", "GitHub profile", "Name on profile", "Repo access", "Scrum role"], [
    ["BA05010", "Ashish Kumar Shrivastava", gh("Ashishshri10"), "Ashish Kumar Shrivastava", "Write", "Developer"],
    ["BA05015", "C. Prashanth", gh("cprashanth666666-sys"), "Not set", "Admin (owner)", "Scrum Master"],
    ["BA05023", "Ishwarya Lakshmi V", gh("IshwaryaLaksh"), "Ishwarya Lakshmi", "Write", "Developer"],
    ["BA05047", "Reva Pradeep", gh("Reva-Pradeep"), "Reva Pradeep", "Write", "Developer"],
    ["BA05054", "Shwetha Shyam Mathew", gh("shwetha123920"), "Not set", "Write", "Product Owner"],
  ], [950, 2000, 2000, 1700, 1250, 1000]),
  source("Source: GitHub REST API, users/{login}, repos/…/collaborators and repos/…/invitations, read 24 Nov 2026."),
  p("Progress is measured in story points of finished stories, where finished means the Definition of Done is met: the notebook ran end to end on Databricks and its checks passed. Figure 3 and Table 6 count each member’s owned stories as recorded in the tracker. 70 of 78 points (90%) are done."),
  image(path.join(__dirname, "fig_member_progress.png"), 560),
  figureCaption("Story points done and open, by owner"),
  source("Source: owner and points per story from docs/TEAM_PROGRESS.md and PROJECT_PLAN.md; done = closed issue with notebook run-verified on 16 Nov or earlier; story 7.1 (dashboard) published and checked on 24 Nov. Computed in docs/report/make_cp4_charts.py."),
  tableCaption("Progress by member"),
  table("T6", ["Member", "Stories owned", "Points done", "Points open", "Complete"], [
    [gh("shwetha123920"), "2.1, 2.2, 2.3, 4.1, 4.2", "17", "0", "100%"],
    [gh("Reva-Pradeep"), "3.1, 3.2, 3.3", "13", "0", "100%"],
    [gh("IshwaryaLaksh"), "5.1, 5.2, 5.3, 5.4", "18", "0", "100%"],
    [gh("Ashishshri10"), "6.1, 6.2, 7.1, 7.2", "11", "5", "69%"],
    [gh("cprashanth666666-sys"), "1.1, 1.2, 1.3, 1.4, 7.3", "11", "3", "79%"],
    ["Team", "21 stories", "70", "8", "90%"],
  ], [2400, 2700, 1200, 1200, 1100]),
  source("Check: 17 + 13 + 18 + 11 + 11 = 70; 0 + 0 + 0 + 5 + 3 = 8; 70 + 8 = 78 = plan total. Caution: these are owned points from the tracker, not authorship. Every commit is from one account, so peer ratings and the learning log must carry individual credit."),
  h2("Burndown"),
  p("Figure 4 plots points remaining. The red line counts a story when its notebook was committed; the blue line counts it only when it met the Definition of Done on Databricks. The gap between them from 7 to 16 November is notebooks 06 to 08, which were written but not run until the 16 November job. With the dashboard published on 24 November, eight points remain, all in the delivery epic: the final report (7.2) and the benchmark (7.3), both due after Checkpoint 4."),
  image(path.join(__dirname, "fig_burndown.png"), 580),
  figureCaption("Sprint burndown, 3 to 29 November 2026"),
  source("Source: commit dates from git log; Definition-of-Done dates from PROJECT_PLAN.md section 6; plan dates from Table 7. Computed in docs/report/make_cp4_charts.py."),
];

// ---------- 5. work distribution ----------
const s5 = [
  h1("5. Distribution of the Remaining Work"),
  p("Eight points remain after the dashboard (7.1) closed on 24 November, all in the delivery epic, plus submission tasks that carry no points. Before this plan, ten of the then thirteen open points sat with one member. Table 7 spreads them so that every member owns one piece of the finish and can present it at the viva, where any member can be asked about any step. Stories 7.2 and 7.3 change owner; the team should confirm this at today’s stand-up."),
  tableCaption("Remaining work, owners and due dates"),
  table("T7", ["Task", "Story", "Owner", "Support", "Pts", "Due", "Done when"], [
    ["Review the published dashboard; add screenshots to the final report and viva deck", "7.1", gh("Ashishshri10"), "IshwaryaLaksh", "–", "25 Nov", "Screenshots in the report"],
    ["Export notebooks 00–15 as .ipynb; upload files named T04_CP4_*", "CP4", gh("cprashanth666666-sys"), "Ashishshri10", "–", "24 Nov, 6 pm", "Exported 24 Nov (notebooks_ipynb/); upload pending"],
    ["One-page governance note as its own file", "CP4", gh("Reva-Pradeep"), "shwetha123920", "–", "24 Nov, 6 pm", "T04_CP4_Governance.pdf uploaded"],
    ["Commit own work from own GitHub account (all now have write access)", "Team", "Each member", "–", "–", "From 24 Nov", "Commits show each author"],
    ["Review the Gold figures in Table 4 against the dashboard before the final report", "7.2", gh("shwetha123920"), "cprashanth666666-sys", "–", "25 Nov", "Figures match the dashboard"],
    ["Benchmark one heavy job (notebook 11 or 12) with and without year partitioning and broadcast join", "7.3", gh("IshwaryaLaksh"), "cprashanth666666-sys", "3", "26 Nov", "Timings table in the report"],
    ["Final report: findings, recommendation, limits, after-project gap ratings", "7.2", gh("shwetha123920"), "All five", "3", "27 Nov, 6 pm", "4–6 pages uploaded"],
    ["Viva deck and demo script; every member speaks", "7.2", gh("Reva-Pradeep"), "All five", "2", "29 Nov", "Full rehearsal held"],
    ["After-project skill ratings, learning-log entries, peer ratings", "Team", "Each member", "–", "–", "25 Nov", "Ratings in the gap matrix"],
    ["Assign issues #19–#21 on GitHub; merge main into prashbigdata; record the role swap", "Team", gh("cprashanth666666-sys"), "–", "–", "24 Nov", "Board and tracker match this table"],
  ], [2300, 550, 1750, 1300, 400, 1250, 1350]),
  source("Source: open stories from PROJECT_PLAN.md; deliverables and dates from the Student Guide (CP4 24 Nov, final report 27 Nov, presentations 30 Nov to 2 Dec). Owners are a proposal for the team to confirm."),
  tableCaption("Open points per member after redistribution"),
  table("T8", ["Member", "Open points", "Open tasks"], [
    [gh("Ashishshri10"), "5", "7.1 dashboard"],
    [gh("shwetha123920"), "3", "7.2 final report; Gold figures"],
    [gh("IshwaryaLaksh"), "3", "7.3 benchmark"],
    [gh("Reva-Pradeep"), "2", "7.2 viva deck; governance note"],
    [gh("cprashanth666666-sys"), "0", "CP4 packaging, GitHub housekeeping"],
  ], [2900, 1300, 4700]),
  source("Check: 5 + 3 + 3 + 2 + 0 = 13 open points, matching Table 6."),
];

// ---------- 6. governance (one page) ----------
const s6 = [
  h1("6. Data Governance Note"),
  h2("Licence"),
  p("GHCN-Daily is released under a CC0 1.0 public-domain dedication. NASS Quick Stats and the Census gazetteer are US government works with no licence file, so the team credits both publishers. Databricks Free Edition is licensed for learning only, so the premiums in this project are a study result, not a commercial quote."),
  h2("Privacy"),
  p("The project uses no personal data. Weather is measured at stations and yields are county totals. NASS withholds some county values as “(D)” to avoid revealing individual farms. The pipeline drops these values and never tries to work them out from state totals."),
  h2("Bias"),
  bullet("Coverage bias: counties without a usable station within 30 km cannot be scored, so results describe well-covered counties. Notebook 07 lists the excluded counties."),
  bullet("Scope bias: five Corn Belt states, two crops, county-crops with at least 15 yield years (trend fit) and 12 matched weather-and-yield years (trigger scoring). Results do not carry over to other regions or crops."),
  bullet("Method bias: thresholds are set on the same years they are tested on, which flatters the trigger; irrigated and non-irrigated yields are not separated."),
  h2("Data quality"),
  bullet("Weather values that fail NOAA’s quality checks are dropped, not set to zero; in 2019 to 2025, 99.9% of values passed."),
  bullet("A station-year is used only if at least 90% of growing-season days have both rainfall and temperature; missing days are not filled in."),
  bullet("Only numeric survey yields are kept; dq_report records null rates, quality-flag shares, station coverage by state and the share of withheld yields."),
  bullet("Every notebook asserts its output and recomputes one key figure a second way; notebook 15 re-checks all modules (46 of 46 passed)."),
];

// ---------- 7. India pilot ----------
const s7 = [
  h1("7. Next Step: Extending the Model to India"),
  p("The same question applies in India, where the government already sells weather-index cover under the Restructured Weather Based Crop Insurance Scheme (RWBCIS) and caps the farmer’s Kharif premium at 2% of the sum insured (PIB, 29 August 2026). A pilot started on 24 November, outside the Checkpoint 4 scope. Its first test changed the design: the GHCN weather data already loaded holds 3,807 Indian station IDs, but only about 143 report in a year, too few for about 780 districts. The pilot therefore uses the India Meteorological Department’s gridded weather instead of stations."),
  tableCaption("India pilot: data and results built and checked on Databricks (24 Nov 2026)"),
  table("T9", ["Layer", "Source", "Delta table (notebook)", "Status and check"], [
    ["Weather", "IMD gridded daily rainfall 0.25°, temperature 1.0°", "imd_rain_daily, imd_temp_daily (16)", "36 years (1990–2025): 65.3 million rain rows over 4,964 land cells, 4.6 million temperature rows. 2023 June–September mean 811 mm against IMD’s official 820 mm"],
    ["Yield", "DES district Kharif area, production and yield, six crops, 1997–2022", "in_district_yields (17)", "52,149 rows fetched, none lost in loading; production ÷ area reproduces the published yield"],
    ["Districts", "geoBoundaries ADM2 (ODbL), 735 districts", "in_districts, in_district_cells (18)", "Every district has at least one weather cell (median 5); district areas sum to 3.29 million km², India’s official area is 3.287"],
    ["Name match", "DES names to boundary names", "in_district_xwalk (18)", "633 of 729 yield districts matched (91.6% of yield rows); the rest are mostly districts created after the boundary release"],
    ["Features", "June–September rain, phase rain, dry spell (≤ 2.5 mm), onset, excess, heat", "in_district_year_weather (19)", "26,460 district-years; the driest years, 2002 and 2009, are IMD’s two monsoon droughts"],
    ["Losses", "85% of trend, and PMFBY best 5 of 7 years × 70/80/90%", "in_district_yield_trend (20)", "17–29% of district-years are losses (US: 9–10%); rice lowest"],
    ["Basis risk", "Same scoring as notebook 11", "in_best_trigger_state (21)", "Best trigger per state misses 57% of losses vs 73% at random; season rain misses 62% in six rain-fed states vs 69% elsewhere; 72% in districts < 2,000 km², 63% in those ≥ 10,000 km²"],
    ["Pricing", "Burn cost, % of sum insured", "in_premium_district (22)", "Trigger premium 8–9% vs the 2% farmer cap; pays 25–42% of a PMFBY-style shortfall"],
  ], [1100, 2600, 2100, 3100]),
  source("Sources: IMD Pune gridded data archive; DES, Ministry of Agriculture & Farmers Welfare, APY reports; geoBoundaries gbOpen IND; IMD 2023 Southwest Monsoon End of Season Report. Plan, data list and design changes: docs/INDIA_EXPANSION_PLAN.md."),
  p("Because the best trigger per state still misses more than half of losses and costs four to seven times the farmer’s 2% cap, we read the India result as support for a weather trigger as a fast top-up to PMFBY in rain-fed states, not a replacement, with the limit that thresholds are in-sample and one June–September window is used for every state. Next: per-state season windows, a district alias table, rupee pricing from MSP, and an India dashboard page. Full results: docs/report/india_results_24nov.md."),
];

const refs = [
  h1("References"),
  ...[
    "Menne, M. J., et al. (2012). Global Historical Climatology Network – Daily (GHCN-Daily), Version 3 [Data set]. NOAA NCEI. https://doi.org/10.7289/V5D21VHZ",
    "US Census Bureau. (2024). 2024 Gazetteer files: Counties [Data set].",
    "USDA National Agricultural Statistics Service. (2026). Quick Stats bulk data files [Data set; crops file, 3 November 2026].",
    "XIME. (2026). Big Data Project Work: Student Guide (ABDA Skill-Gap Capstone), 20 October 2026.",
    "Team No. 4. (2026). bigdata-noaa-ghcn repository, docs/PROJECT_PLAN.md and docs/TEAM_PROGRESS.md. GitHub.",
  ].map((t) => new Paragraph({ children: [new TextRun({ text: t, font: FONT, size: 20 })],
    indent: { left: 360, hanging: 360 }, spacing: { after: 60, line: 260, lineRule: LineRuleType.AUTO } })),
];

// ---------- document ----------
const border = { style: BorderStyle.SINGLE, size: 18, color: "000000", space: 24 };
const doc = new Document({
  creator: "Team No. 4", title: "Checkpoint 4: Pipeline, Dashboard and AI/ML Model",
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] }] },
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: "000000" }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 24, bold: true, color: "000000" }, paragraph: { outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      titlePage: true,
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 }, pageNumbers: { start: 0 },
        borders: { pageBorders: { display: PageBorderDisplay.ALL_PAGES, offsetFrom: PageBorderOffsetFrom.TEXT },
          pageBorderTop: border, pageBorderBottom: border, pageBorderLeft: border, pageBorderRight: border } },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 20, font: FONT })] })] }),
      first: new Footer({ children: [new Paragraph({ children: [] })] }),
    },
    children: [...cover, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...refs],
  }],
});

// docx-js writes <w:highlightCs/>, which the OOXML schema rejects; strip it (the plain highlight stays).
const JSZip = require(require.resolve("jszip", { paths: [path.dirname(require.resolve("docx"))] }));
Packer.toBuffer(doc).then(async (raw) => {
  const zip = await JSZip.loadAsync(raw);
  const xml = await zip.file("word/document.xml").async("string");
  zip.file("word/document.xml", xml.replace(/<w:highlightCs [^>]*\/>/g, ""));
  const buf = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
  fs.writeFileSync(OUT, buf);
  console.log("widths:", widthLog.join(" "), `| tables ${tableNo}, figures ${figureNo}`);
  console.log("wrote", OUT);
});
