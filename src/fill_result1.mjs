import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/风眠/2026MMC_final/materials/result1.xlsx";
const templatePath = "C:/Users/风眠/2026MMC_final/tmp/result1_template/materials/result1.xlsx";
const schedulePath = "C:/Users/风眠/2026MMC_final/outputs/q1_milp_schedule.csv";
const previewDir = "C:/Users/风眠/2026MMC_final/tmp/q1_result1_preview";
const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const csv = (await fs.readFile(schedulePath, "utf8")).replace(/^\uFEFF/, "");
const rows = csv.trim().split(/\r?\n/).slice(1).map(line => line.split(","));
if (rows.length !== 144) throw new Error(`MILP明细应为144行，实际${rows.length}行`);
const purchase = rows.map(r => Number(r[5]));
const charge = rows.map(r => Number(r[6]));
const discharge = rows.map(r => Number(r[7]));
const initialEnergy = Number(rows[0][9]);
const finalEnergy = Number(rows.at(-1)[10]);

const purchaseSheet = workbook.worksheets.getItem("计划购电量");
const batterySheet = workbook.worksheets.getItem("充放电量");
// Do not write any template labels. Map natural-day results back to source order.
purchaseSheet.getRange("B2:B145").values = [...purchase.slice(1), purchase[0]].map(v => [v]);
purchaseSheet.getRange("B2:B145").format.numberFormat = "0.0000";

const blockSum = (values, block) => {
  let total = 0;
  for (let i = block * 24; i < (block + 1) * 24; i++) total += values[i];
  return total;
};
const batteryBlocks = Array.from({length: 6}, (_, block) => [
  blockSum(charge, block), blockSum(discharge, block)
]);
batterySheet.getRange("B2:C7").values = batteryBlocks;
batterySheet.getRange("B2:C7").format.numberFormat = "0.0000";
batterySheet.getRange("E2:E3").values = [[initialEnergy], [finalEnergy]];
batterySheet.getRange("E2:E3").format.numberFormat = "0.0000";

workbook.recalculate();
const checkPurchase = await workbook.inspect({kind:"table",range:"计划购电量!A1:B145",include:"values,formulas",tableMaxRows:145,tableMaxCols:2,maxChars:18000});
const checkBattery = await workbook.inspect({kind:"table",range:"充放电量!A1:E7",include:"values,formulas",tableMaxRows:8,tableMaxCols:5,maxChars:5000});
const errors = await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:100},summary:"final formula error scan"});
console.log(checkPurchase.ndjson);
console.log(checkBattery.ndjson);
console.log(errors.ndjson);

await fs.mkdir(previewDir, {recursive:true});
for (const sheetName of ["计划购电量", "充放电量"]) {
  const preview = await workbook.render({sheetName, autoCrop:"all", scale:1, format:"png"});
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(inputPath);
console.log(JSON.stringify({
  output: inputPath,
  totalPurchase: purchase.reduce((a,b)=>a+b,0),
  totalCost: rows.reduce((a,r)=>a+Number(r[11]),0),
  totalCharge: charge.reduce((a,b)=>a+b,0),
  totalDischarge: discharge.reduce((a,b)=>a+b,0),
  initialEnergy,
  finalEnergy,
}));
