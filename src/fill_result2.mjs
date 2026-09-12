import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/风眠/2026MMC_final";
const inputPath = `${root}/materials/result2.xlsx`;
const schedulePath = `${root}/outputs/q2/q2_schedule.csv`;
const planPath = `${root}/outputs/q2/result2_plan_rows.json`;
const previewDir = `${root}/tmp/q2_result2_filled_preview`;

function parseCsvLine(line) {
  const cells = [];
  let current = "", quoted = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') { current += '"'; i++; }
      else quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current); current = "";
    } else current += char;
  }
  cells.push(current);
  return cells;
}

function excelSerial(isoDate) {
  return Date.parse(`${isoDate}T00:00:00Z`) / 86400000 + 25569;
}

function clock(slot) {
  const minutes = slot * 10;
  if (minutes === 1440) return "24:00";
  return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`;
}

const csv = (await fs.readFile(schedulePath, "utf8")).replace(/^\uFEFF/, "");
const parsed = csv.trim().split(/\r?\n/).slice(1).map(parseCsvLine);
if (parsed.length !== 334 * 144) {
  throw new Error(`第二问明细应为48096行，实际${parsed.length}行`);
}
const days = Array.from({ length: 334 }, (_, d) => parsed.slice(d * 144, (d + 1) * 144));
for (const day of days) {
  if (day.length !== 144 || new Set(day.map(row => row[0])).size !== 1) {
    throw new Error("第二问明细的日期分组不完整");
  }
}
const planData = JSON.parse(await fs.readFile(planPath, "utf8"));
if(planData.time_axis !== "shifted_0010") throw new Error("Wrong plan time axis");

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const purchaseSheet = workbook.worksheets.getItem("计划购电量");
const batterySheet = workbook.worksheets.getItem("充放电量");
const emergencySheet = workbook.worksheets.getItem("紧急购电量");

// Each complete row was optimized at this date's 00:00.
const planRows = days.map((day, d) => {
  if(planData.dates[d] !== day[0][0]) throw new Error("Date mismatch");
  const values = planData.purchase[d];
  const total = values.reduce((sum, value) => sum + value, 0);
  const cost = values.reduce((sum, value, i) => sum + value * planData.prices[i], 0);
  return [...values, total, cost];
});
purchaseSheet.getRange("B2:EQ335").values = planRows;
purchaseSheet.getRange("B2:EQ335").format.numberFormat = "0.0000";

const blocks = ["0:00-4:00", "4:00-8:00", "8:00-12:00",
  "12:00-16:00", "16:00-20:00", "20:00-24:00"];
const batteryRows = [];
for (const day of days) {
  const iso = day[0][0];
  for (let block = 0; block < 6; block++) {
    const segment = day.slice(block * 24, (block + 1) * 24);
    batteryRows.push([
      block === 0 ? excelSerial(iso) : null,
      blocks[block],
      segment.reduce((sum, row) => sum + Number(row[9]), 0),
      segment.reduce((sum, row) => sum + Number(row[10]), 0),
      block === 0 ? "0:00" : block === 1 ? "24:00" : null,
      block === 0 ? Number(day[0][13]) : block === 1 ? Number(day[143][14]) : null,
    ]);
  }
}
for (let d = 1; d < days.length; d++) {
  batterySheet.getRangeByIndexes(1 + d * 6, 0, 6, 6)
    .copyFrom(batterySheet.getRange("A2:F7"), "all");
}
batterySheet.getRange(`A2:F${batteryRows.length + 1}`).values = batteryRows;
batterySheet.getRange(`A2:A${batteryRows.length + 1}`).format.numberFormat = "m/d/yy";
batterySheet.getRange(`C2:D${batteryRows.length + 1}`).format.numberFormat = "0.0000";
batterySheet.getRange(`F2:F${batteryRows.length + 1}`).format.numberFormat = "0.0000";

const oldEmergencyRows = emergencySheet.getUsedRange().rowCount;
emergencySheet.getRange(`A2:C${Math.max(oldEmergencyRows,2)}`).values = [[null]];
const emergencyRows = [];
for (const day of days) {
  let firstForDate = true;
  for (let start = 0; start < 144;) {
    if (Number(day[start][11]) <= 1e-7) { start++; continue; }
    let end = start + 1;
    let quantity = Number(day[start][11]);
    while (end < 144 && Number(day[end][11]) > 1e-7) {
      quantity += Number(day[end][11]);
      end++;
    }
    emergencyRows.push([
      firstForDate ? excelSerial(day[0][0]) : null,
      `${clock(start)}-${clock(end)}`,
      quantity,
    ]);
    firstForDate = false;
    start = end;
  }
}
for (let row = 1; row < emergencyRows.length; row++) {
  emergencySheet.getRangeByIndexes(1 + row, 0, 1, 3)
    .copyFrom(emergencySheet.getRange("A2:C2"), "all");
}
emergencySheet.getRange(`A2:C${emergencyRows.length + 1}`).values = emergencyRows;
emergencySheet.getRange(`A2:A${emergencyRows.length + 1}`).format.numberFormat = "m/d/yy";
emergencySheet.getRange(`C2:C${emergencyRows.length + 1}`).format.numberFormat = "0.0000";

workbook.recalculate();
const checks = [];
for (const [sheet, range] of [
  ["计划购电量", "A1:EQ4"],
  ["充放电量", "A1:F14"],
  ["紧急购电量", "A1:C20"],
]) {
  const result = await workbook.inspect({
    kind: "table", range: `${sheet}!${range}`, include: "values,formulas",
    tableMaxRows: 20, tableMaxCols: 147, maxChars: 24000,
  });
  checks.push({ sheet, inspection: result.ndjson });
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "result2 final formula error scan",
});

await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["计划购电量", "充放电量", "紧急购电量"]) {
  const preview = await workbook.render({ sheetName, range: sheetName === "计划购电量" ? "A1:H6" : sheetName === "充放电量" ? "A1:F14" : "A1:C16", scale: 1.5, format: "png" });
  await fs.writeFile(
    path.join(previewDir, `${sheetName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(inputPath);

const summary = {
  output: inputPath,
  plan_days: planRows.length,
  battery_rows: batteryRows.length,
  emergency_rows: emergencyRows.length,
  first_plan_date: days[0][0][0],
  last_plan_date: days.at(-1)[0][0],
  final_template_interval_purchase_kwh: planData.purchase.at(-1).at(-1),
  displayed_plan_purchase_kwh: planRows.reduce((sum, row) => sum + row[144], 0),
  displayed_plan_cost_yuan: planRows.reduce((sum, row) => sum + row[145], 0),
  inspections: checks,
  formula_errors: errors.ndjson,
};
await fs.writeFile(
  `${root}/outputs/q2/result2_fill_summary.json`,
  JSON.stringify(summary, null, 2), "utf8",
);
console.log(JSON.stringify({ ...summary, inspections: "saved in summary" }, null, 2));
