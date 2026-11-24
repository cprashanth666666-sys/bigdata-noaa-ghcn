// Builds docs/T04_Final_Report.docx: the Big Data Project Work final report, Team No. 4.
// Run from docs/report:  NODE_PATH="<global node_modules>" node build_final_report.js
// Format: XIME house style (A4, 1" margins, Times New Roman 12 pt, 1.5 spacing, page border,
// unnumbered cover). Content follows the five items the Student Guide requires for the final report.
// Gold results were filled 24 Nov 2026 (docs/report/results_24nov.md). The after-project skill ratings are a
// yellow-highlighted "[TO FILL ...]" placeholder. Never replace one with a number that did not come
// from a notebook run or a member's own rating.

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, AlignmentType, PageBreak, Footer, ImageRun, LevelFormat, PageNumber, LineRuleType,
  BorderStyle, PageBorderDisplay, PageBorderOffsetFrom, ExternalHyperlink,
} = require("docx");
const fs = require("fs");
const path = require("path");

const FONT = "Times New Roman";
const GREY = "595959";
const OUT = path.join(__dirname, "..", "T04_Final_Report.docx");
const PRINTABLE = 11906 - 2 * 1440; // A4 width minus 1" margins = 9026 twips
const SAFE = 8950;

// ---------- helpers ----------
const BODY = { after: 160, line: 360, lineRule: LineRuleType.AUTO };
const TODO = /\[TO FILL[^\]]*\]/;

// A run, highlighted yellow when it is a placeholder.
function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, size: 24, ...opts, ...(TODO.test(text) ? { highlight: "yellow" } : {}) });
}
// Split text so every "[TO FILL ...]" piece is its own highlighted run.
function runs(text, opts = {}) {
  return text.split(/(\[TO FILL[^\]]*\])/).filter(Boolean).map((t) => run(t, opts));
}
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 28, font: FONT, color: "000000" })],
    spacing: { before: 280, after: 120, line: 300, lineRule: LineRuleType.AUTO },
    keepNext: true,
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 24, font: FONT, color: "000000" })],
    spacing: { before: 160, after: 80, line: 300, lineRule: LineRuleType.AUTO },
    keepNext: true,
  });
}
function p(text, opts = {}) {
  return new Paragraph({ children: runs(text, opts), alignment: AlignmentType.JUSTIFIED, spacing: BODY });
}
function pChildren(children) {
  return new Paragraph({ children, alignment: AlignmentType.JUSTIFIED, spacing: BODY });
}
function bullet(text) {
  return new Paragraph({
    children: runs(text),
    numbering: { reference: "bullets", level: 0 },
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 60, line: 330, lineRule: LineRuleType.AUTO },
  });
}
function link(text, url) {
  return new ExternalHyperlink({ link: url, children: [new TextRun({ text, font: FONT, size: 24, style: "Hyperlink" })] });
}

// One Paragraph per line: a "\n" inside one TextRun does not break the line in OOXML.
function cell(text, { header = false, width, shade } = {}) {
  const lines = String(text).split("\n");
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: shade ? { type: ShadingType.CLEAR, fill: shade } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: lines.map((line) => new Paragraph({
      alignment: AlignmentType.LEFT,
      spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO },
      children: line.split(/(\[TO FILL[^\]]*\])/).filter(Boolean).map((t) => new TextRun({
        text: t, bold: header, size: 19, font: FONT, color: header ? "FFFFFF" : "000000",
        ...(TODO.test(t) ? { highlight: "yellow" } : {}),
      })),
    })),
  });
}
const widthsChecked = [];
function table(label, headers, rows, widths) {
  const sum = widths.reduce((a, b) => a + b, 0);
  if (sum > SAFE) throw new Error(`${label}: column widths sum to ${sum} twips, over the ${SAFE} limit (printable ${PRINTABLE})`);
  rows.forEach((r, i) => { if (r.length !== widths.length) throw new Error(`${label}: row ${i} has ${r.length} cells, expected ${widths.length}`); });
  widthsChecked.push(`${label}: ${sum}`);
  return new Table({
    columnWidths: widths,
    width: { size: sum, type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, { header: true, width: widths[i], shade: "000000" })) }),
      ...rows.map((r, idx) => new TableRow({
        cantSplit: true,
        children: r.map((c, i) => cell(c, { width: widths[i], shade: idx % 2 ? "F2F2F2" : "FFFFFF" })),
      })),
    ],
  });
}
let tableNo = 0, figureNo = 0;
function tableCaption(text) {
  tableNo += 1;
  return new Paragraph({
    keepNext: true,
    children: [new TextRun({ text: `Table ${tableNo}. ${text}`, bold: true, size: 20, font: FONT })],
    spacing: { before: 160, after: 60 },
  });
}
function figureCaption(text) {
  figureNo += 1;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: `Figure ${figureNo}. ${text}`, bold: true, size: 20, font: FONT })],
    spacing: { after: 60 },
  });
}
function source(text) {
  return new Paragraph({
    children: text.split(/(\[TO FILL[^\]]*\])/).filter(Boolean).map((t) => new TextRun({
      text: t, size: 18, italics: true, color: GREY, font: FONT, ...(TODO.test(t) ? { highlight: "yellow" } : {}),
    })),
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 260, lineRule: LineRuleType.AUTO },
  });
}
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function image(file, widthPx) {
  const { w, h } = pngSize(file);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: true,
    spacing: { before: 80, after: 40 },
    children: [new ImageRun({ data: fs.readFileSync(file), transformation: { width: widthPx, height: Math.round(widthPx * h / w) }, type: "png" })],
  });
}
function centre(text, opts = {}, spacing = {}) {
  return new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text, font: FONT, size: 24, ...opts })], spacing });
}

const POSTING = "https://amazon.jobs/en/jobs/10582732/data-engineer-i";
const REPO = "https://github.com/cprashanth666666-sys/bigdata-noaa-ghcn/tree/prashbigdata";
const AFTER = "[TO FILL]";

// ---------- cover ----------
const cover = [
  new Paragraph({ spacing: { before: 400 }, children: [] }),
  centre("A Project Report on", { size: 26 }, { after: 240 }),
  centre("“Parametric Weather Insurance for US Crop Risk: Quantifying Basis Risk with Big Data on Databricks”",
    { size: 30, bold: true, italics: true }, { after: 200, line: 360, lineRule: LineRuleType.AUTO }),
  centre("Final Report", { size: 26, bold: true }, { after: 60 }),
  centre("Big Data Project Work: ABDA Skill-Gap Capstone", { size: 24 }, { after: 240 }),
  centre("Team No. 4", { size: 26, bold: true }, { after: 240 }),
  centre("Submitted to", { size: 24 }, { after: 60 }),
  centre("Xavier Institute of Management & Entrepreneurship, Bangalore", { size: 26, bold: true }, { after: 240 }),
  centre("A Project Report submitted in partial fulfilment of the Big Data Project Work requirement, Business Analytics (PGDM)",
    { size: 22, italics: true }, { after: 200, line: 300, lineRule: LineRuleType.AUTO }),
  centre("Under the guidance of", { size: 22, italics: true }, { after: 80 }),
  centre("Nikhil D Johnathan", { size: 26, bold: true }, { after: 40 }),
  centre("Course instructor, XIME", { size: 22, italics: true }, { after: 200 }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 60 },
    children: [new TextRun({ text: "Code repository (branch prashbigdata): ", font: FONT, size: 22 }),
      new ExternalHyperlink({ link: REPO, children: [new TextRun({ text: "github.com/cprashanth666666-sys/bigdata-noaa-ghcn", font: FONT, size: 22, style: "Hyperlink" })] })],
  }),
  centre("27 November 2026", { size: 22 }, { after: 240 }),
  new Table({
    alignment: AlignmentType.CENTER,
    columnWidths: [2200, 4200],
    width: { size: 6400, type: WidthType.DXA },
    rows: [["Roll No.", "Name"], ["BA05010", "Ashish Kumar Shrivastava"], ["BA05015", "C. Prashanth"],
      ["BA05023", "Ishwarya Lakshmi V"], ["BA05047", "Reva Pradeep"], ["BA05054", "Shwetha Shyam Mathew"]]
      .map((r, i) => new TableRow({ children: r.map((c, j) => cell(c, { header: i === 0, width: [2200, 4200][j], shade: i === 0 ? "000000" : undefined })) })),
  }),
  new Paragraph({ spacing: { before: 360 }, children: [] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [new ImageRun({ data: fs.readFileSync(path.join(__dirname, "xime_logo.png")), transformation: { width: 300, height: Math.round(300 / 3.386) }, type: "png" })],
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- 1. posting and gap matrix ----------
const s1 = [
  h1("1. The Job Posting and Our Skill Gaps"),
  pChildren([
    ...runs("Our client brief is Amazon’s Data Engineer I posting for the Data Insights, Metrics and Reporting team in Bengaluru (Job ID 10582732), taken from the company’s own careers site ("),
    link("amazon.jobs", POSTING),
    ...runs(") and saved on 27 October 2026. It asks for SQL and data modelling, Big Data and MPP systems, ETL pipelines, AWS data services and test automation, and for the ability to explain data to non-technical customers. Table 1 compares the team’s ratings at Checkpoint 1 with the ratings after the project, and names the work that moved each skill."),
  ]),
  tableCaption("Gap matrix for the Amazon Data Engineer I posting, before and after the project"),
  table("Table 1", ["Skill in the posting", "Type", "Avg before", "Gap before", "Avg after", "Gap after", "Project evidence"], [
    ["SQL (query language)", "Must", "1.8", "2.4", AFTER, AFTER, "SQL checks that recompute key figures (notebooks 03, 05, 09, 12); eight dashboard views (14)"],
    ["Python (scripting)", "Must", "1.4", "3.2", AFTER, AFTER, "PySpark in all 16 notebooks (00 to 15)"],
    ["Data modelling and warehousing", "Must", "0.8", "4.4", AFTER, AFTER, "Bronze, Silver and Gold Delta tables, each schema written in the notebook header"],
    ["Building ETL pipelines", "Must", "0.6", "4.8", AFTER, AFTER, "Weather, yield and county files loaded, cleaned, joined and aggregated to Gold (01 to 13)"],
    ["Big Data / MPP systems; distributed storage and query", "Must", "0.0", "6.0", AFTER, AFTER, "263-million-row weather table partitioned by year; broadcast joins; window functions"],
    ["AWS cloud data services (S3, Redshift, Glue)", "Must", "0.0", "6.0", AFTER, AFTER, "Partly closed: weather read from the AWS Open Data S3 bucket; no hands-on Glue or Redshift"],
    ["Test automation (unit and integration tests)", "Must", "0.2", "5.6", AFTER, AFTER, "Partly closed: assert checks and a second-method recomputation in each notebook; no unit-test framework yet"],
    ["Business needs; explaining to non-technical users", "Must", "2.4", "1.2", AFTER, AFTER, "Dashboard and report written for an insurer, not for engineers"],
    ["Hadoop / Hive / Spark / EMR", "Nice", "0.0", "3.0", AFTER, AFTER, "Spark throughout; no Hadoop, Hive or EMR"],
    ["A classic ETL tool (Informatica, SSIS, ODI)", "Nice", "0.0", "3.0", AFTER, AFTER, "Not covered; an honest gap"],
  ], [2050, 560, 700, 700, 700, 700, 3390]),
  source("Sources: “before” ratings from the team’s Checkpoint 1 gap matrix (27 October 2026); “after” ratings are each member’s own rating at the end of the project [TO FILL: enter the five members’ new ratings and recompute]. Scale: 0 = never heard of it, 1 = know the idea, 2 = used it with help, 3 = can do it alone. Gap = importance × (3 − team average), importance 2 for a must-have and 1 for a nice-to-have (Student Guide, worked example 2)."),
  p("The project targeted the three largest gaps: Big Data and MPP systems, AWS cloud data services and test automation. The first is closed by building the whole pipeline in PySpark. The other two are only partly closed, as Table 1 shows. The posting also asks for at least one year of data-engineering experience. No team member has held a data-engineering role, and the project does not change that."),
];

// ---------- 2. problem, data, pipeline ----------
const s2 = [
  h1("2. Business Problem, Data and Pipeline"),
  p("Parametric crop insurance pays automatically when a measured weather value crosses an agreed trigger, so claims are fast and cheap to settle (Barnett and Mahul, 2007). Its weakness is basis risk: a farmer can lose a crop while the index does not pay (a miss), or the index can pay when there was no loss (a false alarm). Basis risk is the main obstacle to index insurance (Jensen et al., 2016; Clarke, 2016)."),
  p("For corn and soybean counties in Iowa, Illinois, Indiana, Minnesota and Nebraska, the project asks four questions. RQ1: which weather trigger best matches yield losses? RQ2: how does basis risk change with distance to the nearest weather station? RQ3: what premium does each trigger imply? RQ4: which counties lack a nearby station to be insured reliably? Figure 1 shows the problem, data and pipeline together."),
  image(path.join(__dirname, "fig1_pipeline.png"), 600),
  figureCaption("Business problem, data and pipeline"),
  source("Source: notebooks 00 to 14 in the project repository (databricks/ folder)."),
  tableCaption("Datasets and licences"),
  table("Table 2", ["Dataset", "Publisher and access", "Licence", "Size"], [
    ["GHCN-Daily (weather)", "NOAA, via the AWS Open Data S3 bucket noaa-ghcn-pds", "CC0 1.0 public-domain dedication", "263.4 million rows for 2019 to 2025, plus US rainfall and temperature back to 2000"],
    ["Quick Stats (crop yields)", "USDA NASS bulk crops file", "US government work; no licence file; source credited", "23.9 million rows; 2.22 million county yields"],
    ["County gazetteer", "US Census Bureau, 2024 files", "US government open data; source credited", "3,222 counties with centroids"],
  ], [1800, 2500, 2200, 2300]),
  source("Sources: Menne et al. (2012); USDA NASS (2026); US Census Bureau (2024). Row counts from the team’s Delta tables, checked with a second query (Checkpoint 2)."),
  p("Silver keeps a station-year only if at least 90% of April to September days have quality-passed rainfall and temperature, and links each county to its nearest such station within 30 km. Gold computes rainfall, heat and dry-spell indices for each county and year, flags a loss year when yield falls below 85% of the county’s own trend, and scores five indices at five payout frequencies against those losses. The work uses the big-data techniques the posting names: a year-partitioned Delta table, broadcast joins that avoid shuffling the 263-million-row table, window functions for station ranking and rolling rainfall, and filters applied before joins. Each notebook asserts its own output (no duplicates, no impossible values) and recomputes one key figure a second way."),
];

// ---------- 3. findings ----------
const s3 = [
  h1("3. Key Findings and Recommendation"),
  p("Notebooks 06 to 15 ran as Databricks jobs on 16 November 2026 and all 46 validation checks passed. Table 3 gives the results; each headline figure was re-derived a second way from the Gold tables."),
  tableCaption("Findings by research question"),
  table("Table 3", ["Question", "Measure", "Source table (notebook)", "Result"], [
    ["Loss years", "Share of county-years below 85% of trend", "county_yield_trend (10)", "Corn 9.1% (977 of 10,768); soybeans 10.4% (1,078 of 10,420). In 2012, 65% of corn county-years were losses"],
    ["RQ1: best trigger", "Lowest pooled miss rate with false-alarm rate at most 25%, per state and crop", "best_trigger_region (11)", "Heat days win in IL, IN and IA; rainfall wins in MN and NE. Miss rate 10.9% (IN corn) to 54.8% (MN corn), vs 69% to 74% by chance"],
    ["RQ2: basis risk and distance", "Miss rate in 0–10, 10–20 and 20–30 km bands; station correlation against distance", "trigger_eval_dist_band (11); corr_distance_curve (12)", "Corn heat trigger flat at 32–33%; rainfall trigger 53%, 51%, 64%. Rainfall correlation 0.91 to 0.80 within 40 km; heat stays near 0.89"],
    ["RQ3: premium", "Premium rate and USD per acre; worst-year payout and loss ratio", "premium_county; portfolio_summary (13)", "Median rate 8.5% corn, 9.1% soybeans (USD 62 and 49 per acre). Worst year 2012: payouts 2.7 times a year’s premium"],
    ["RQ4: coverage gaps", "Counties with no usable station within 30 km", "county_coverage_gaps (07)", "87 of 470 Corn Belt counties never covered; 155 covered in under half of years"],
  ], [1700, 2700, 2000, 2400]),
  source("Source: Gold tables in workspace.default, queried 24 Nov 2026; re-checks in docs/report/results_24nov.md. Dollar figures assume one insured acre per county and illustrative prices."),
  image(path.join(__dirname, "fig2_distance.png"), 580),
  figureCaption("Basis risk and weather similarity by distance"),
  source("Source: trigger_eval_dist_band (corn, trigger pays in 20% of years) and corr_distance_curve. The 20–30 km band holds only 36 corn loss years."),
  h2("Recommendation"),
  p("Because the data shows that heat-day triggers miss about one loss in three and do not get worse with distance, while rainfall triggers miss about half of losses and degrade beyond 20 km, we recommend that the insurer sell heat-day triggers in Illinois, Indiana and Iowa and offer rainfall cover in Minnesota and Nebraska only where a usable station is within 20 km, with the limit that thresholds were fitted on the same years they were tested on, so real miss rates will be higher."),
  h2("Limits"),
  bullet("Trigger thresholds are set from the same years they are tested on, so the miss rates are optimistic. An out-of-sample test is the next step."),
  bullet("Each county counts as one insured acre, because no acreage data is joined. Dollar figures show the shape of the risk, not real exposure."),
  bullet("Crop prices (USD 4.50 per bushel of corn, USD 11.00 for soybeans), the 25% payout share and the 25% loading in notebook 13 are illustrative assumptions, not market quotes."),
  bullet("Payouts are all-or-nothing, and yields also fall for reasons weather does not capture, such as pests, disease and management. That gap is part of the basis risk being measured."),
  bullet("Weather from 2000 to 2025 gives about 26 years, so a trigger that pays one year in ten has only two or three events per county to learn from."),
];

// ---------- 4. governance ----------
const s4 = [
  h1("4. Governance Note"),
  h2("Licence"),
  p("GHCN-Daily is released under a CC0 1.0 public-domain dedication. NASS Quick Stats and the Census gazetteer are US government works with no licence file, so the team credits both publishers. Databricks Free Edition is licensed for learning only, so the premiums in this report are a study result, not a commercial quote."),
  h2("Privacy"),
  p("The project uses no personal data. Weather is measured at stations and yields are county totals. NASS withholds some county values as “(D)” to avoid revealing individual farms. The pipeline drops these values and never tries to work them out from state totals."),
  h2("Bias"),
  bullet("Coverage bias: counties without a usable station within 30 km cannot be scored, so results describe well-covered counties. Notebook 07 lists the excluded counties (RQ4)."),
  bullet("Scope bias: five Corn Belt states, two crops, and only county-crops with at least 15 yield years. Results do not carry over to other regions or crops."),
  bullet("Method bias: in-sample thresholds flatter the trigger, and irrigated and non-irrigated yields are not separated."),
  h2("Data quality"),
  bullet("Weather values that fail NOAA’s quality checks are dropped, not set to zero; in 2019 to 2025, 99.9% of values passed (Checkpoint 2)."),
  bullet("A station-year is used only if at least 90% of growing-season days have both rainfall and temperature; missing days are not filled in, so seasonal rainfall is a slight underestimate."),
  bullet("Only numeric survey yields are kept. The dq_report table records null rates, quality-flag shares, station coverage by state and the share of withheld yields."),
  bullet("Every notebook asserts its output and recomputes one key figure a second way, for example a county’s nearest station in plain SQL (05) and one dry spell row by row (09)."),
];

// ---------- 5. learning log ----------
const s5 = [
  h1("5. Learning Log Summary"),
  tableCaption("What broke and how we fixed it"),
  table("Table 4", ["What broke", "How we fixed it", "Notebook"], [
    ["Only seven years of weather (2019 to 2025), too few loss years per county", "Extended US rainfall and temperature back to 2000 before any feature work", "03"],
    ["Serverless ANSI mode failed when casting NASS “(D)” markers to numbers", "Used try_cast, which turns the markers into nulls, then dropped them", "02"],
    ["Heat-day counts are zero in many years, so percentile triggers fired far too often", "Dropped any county-trigger that pays in more than 40% of years", "11"],
    ["Notebooks 06 to 08 stayed uncommitted for days after being written", "Commit each notebook the day it is finished", "All"],
    ["Free Edition daily compute quota", "Filter to US stations and growing-season months early; partition by year", "01 to 13"],
    ["First Databricks job run (16 Nov): notebook 11 summary re-aggregated a county table with a row-level column; notebook 07 counted defunct counties as coverage gaps", "Pooled sums in 11; scoped 07 to counties with 2000–2025 yields and a current Census code; added validation notebook 15 (46 of 46 checks)", "07, 11, 15"],
  ], [3300, 4300, 1200]),
  source("Source: team learning log and the project’s git history."),
  p("Next, the team would set thresholds on held-out years, weight counties by planted acres, add pytest unit tests for the cleaning functions (closing the test-automation gap), and run the notebooks in order as a Databricks Job."),
  p("Code, notebook checks and report drafts were written with help from an AI assistant (Claude), as recorded in the learning log. Before the presentation, each member runs the notebooks on their own account so that any member can explain any step."),
];

// ---------- references ----------
const refs = [
  h1("References"),
  ...[
    "Barnett, B. J., & Mahul, O. (2007). Weather index insurance for agriculture and rural areas in lower-income countries. American Journal of Agricultural Economics, 89(5), 1241–1247.",
    "Clarke, D. J. (2016). A theory of rational demand for index insurance. American Economic Journal: Microeconomics, 8(1), 283–306.",
    "Jensen, N. D., Barrett, C. B., & Mude, A. G. (2016). Index insurance quality and basis risk: Evidence from northern Kenya. American Journal of Agricultural Economics, 98(5), 1450–1469.",
    "Menne, M. J., et al. (2012). Global Historical Climatology Network – Daily (GHCN-Daily), Version 3 [Data set]. NOAA National Centers for Environmental Information. https://doi.org/10.7289/V5D21VHZ",
    "US Census Bureau. (2024). 2024 Gazetteer files: Counties [Data set].",
    "USDA National Agricultural Statistics Service. (2026). Quick Stats bulk data files [Data set; crops file, 3 November 2026].",
    "XIME. (2026). Big Data Project Work: Student Guide (ABDA Skill-Gap Capstone), 20 October 2026.",
  ].map((t) => new Paragraph({
    children: [new TextRun({ text: t, font: FONT, size: 20 })],
    indent: { left: 360, hanging: 360 },
    spacing: { after: 60, line: 260, lineRule: LineRuleType.AUTO },
  })),
];

// ---------- document ----------
const doc = new Document({
  creator: "Team No. 4",
  title: "Parametric Weather Insurance for US Crop Risk: Final Report",
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } }] }] },
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
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
        pageNumbers: { start: 0 },
        borders: {
          pageBorders: { display: PageBorderDisplay.ALL_PAGES, offsetFrom: PageBorderOffsetFrom.TEXT },
          pageBorderTop: { style: BorderStyle.SINGLE, size: 18, color: "000000", space: 24 },
          pageBorderBottom: { style: BorderStyle.SINGLE, size: 18, color: "000000", space: 24 },
          pageBorderLeft: { style: BorderStyle.SINGLE, size: 18, color: "000000", space: 24 },
          pageBorderRight: { style: BorderStyle.SINGLE, size: 18, color: "000000", space: 24 },
        },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 20, font: FONT })] })] }),
      first: new Footer({ children: [new Paragraph({ children: [] })] }),
    },
    children: [...cover, ...s1, ...s2, ...s3, ...s4, ...s5, ...refs],
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
  console.log("table widths (twips):", widthsChecked.join("; "));
  console.log(`tables: ${tableNo}, figures: ${figureNo}`);
  console.log("wrote", OUT);
});
