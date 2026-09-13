import fs from 'node:fs/promises';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const root='C:/Users/风眠/2026MMC_final';
const mode=Number(process.argv[2]);
if(![2,3].includes(mode))throw new Error('mode must be 2 or 3');
const file=`${root}/materials/result4-${mode}.xlsx`;
const summary=JSON.parse(await fs.readFile(`${root}/outputs/q4/q${mode}/summary.json`,'utf8'));
if(summary.fixed_model!==0||summary.selection_policy!=='fixed_year')throw new Error('Formal Q4 requires fixed yearly M0');
if(mode===3&&JSON.stringify(summary.update_hours)!=='[6,12]')throw new Error('Formal Q4 Q3 requires 06/12 updates');
const data=JSON.parse(await fs.readFile(`${root}/outputs/q4/q${mode}/workbook_data.json`,'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(file));
const preview=`${root}/tmp/q4_${mode}_preview`;await fs.mkdir(preview,{recursive:true});
if(process.argv.includes('--inspect-only')){
  for(const s of book.worksheets.items){
    const blob=await book.render({sheetName:s.name,range:s.name.includes('购电量')&&s.name!=='紧急购电量'?'A1:H5':s.name==='充放电量'?'A1:F9':'A1:C8',scale:1.3,format:'png'});
    await fs.writeFile(`${preview}/before_${s.name}.png`,new Uint8Array(await blob.arrayBuffer()));
  }
  process.exit(0);
}
const serial=d=>Date.parse(`${d}T00:00:00Z`)/86400000+25569;
const sum=a=>a.reduce((s,v)=>s+v,0);
const clock=t=>`${Math.floor(t/6)}:${String((t%6)*10).padStart(2,'0')}`;
const plan=book.worksheets.getItem('计划购电量');
const adjusted=mode===3?book.worksheets.getItem('调整购电量'):null;
plan.getRange('B2:EQ335').values=data.baseline.map((a,d)=>[...a,sum(a),sum(a.map((v,i)=>v*data.prices[d][i]))]);
// This sheet holds final effective purchase, not a signed adjustment delta.
// Its fee is the entire settled grid fee (including adjustment, excluding emergency).
if(adjusted)adjusted.getRange('B2:EQ335').values=data.final.map((a,d)=>[...a,sum(a),sum(data.grid_fee[d])]);
for(const s of [plan,adjusted].filter(Boolean))s.getRange('B2:EQ335').format.numberFormat='0.0000';
const battery=book.worksheets.getItem('充放电量');
const rows=[];
for(let d=0;d<data.dates.length;d++)for(let j=0;j<6;j++)rows.push([j===0?serial(data.dates[d]):null,`${clock(j*24)}-${clock((j+1)*24)}`,sum(data.charge[d].slice(j*24,(j+1)*24)),sum(data.discharge[d].slice(j*24,(j+1)*24)),j===0?'0:00':j===1?'24:00':null,j===0?data.energy[d][0]:j===1?data.energy[d][144]:null]);
for(let d=1;d<data.dates.length;d++)battery.getRangeByIndexes(1+d*6,0,6,6).copyFrom(battery.getRange('A2:F7'),'all');
battery.getRange(`A2:F${rows.length+1}`).values=rows;
battery.getRange(`A2:A${rows.length+1}`).format.numberFormat='m/d/yy';
battery.getRange(`C2:D${rows.length+1}`).format.numberFormat='0.0000';
battery.getRange(`F2:F${rows.length+1}`).format.numberFormat='0.0000';
const emergency=book.worksheets.getItem('紧急购电量');
const count=emergency.getUsedRange().rowCount;
emergency.getRange(`A2:C${Math.max(count,2)}`).values=[[null]];
const events=[];
for(let d=0;d<data.dates.length;d++){
  let first=true;
  for(let t=0;t<144;){
    if(data.emergency[d][t]<=1e-7){t++;continue;}
    const start=t;let quantity=0;
    while(t<144&&data.emergency[d][t]>1e-7)quantity+=data.emergency[d][t++];
    events.push([first?serial(data.dates[d]):null,`${clock(start)}-${clock(t)}`,quantity]);first=false;
  }
}
for(let i=1;i<events.length;i++)emergency.getRangeByIndexes(i+1,0,1,3).copyFrom(emergency.getRange('A2:C2'),'all');
emergency.getRange(`A2:C${events.length+1}`).values=events;
emergency.getRange(`A2:A${events.length+1}`).format.numberFormat='m/d/yy';
emergency.getRange(`C2:C${events.length+1}`).format.numberFormat='0.0000';
book.recalculate();
const errors=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:50}});
for(const s of book.worksheets.items){
  const range=s.name==='充放电量'?'A1:F14':s.name==='紧急购电量'?'A1:C16':'A1:H6';
  const check=await book.inspect({kind:'table',range:`${s.name}!${range}`,include:'values,formulas',tableMaxRows:16,tableMaxCols:8});
  await fs.writeFile(`${preview}/${s.name}.ndjson`,check.ndjson);
  const blob=await book.render({sheetName:s.name,range,scale:1.5,format:'png'});
  await fs.writeFile(`${preview}/${s.name}.png`,new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(book)).save(file);
const report={plan_days:data.dates.length,battery_rows:rows.length,emergency_rows:events.length,formula_errors:errors.ndjson,
  fee_convention:'plan sheet = baseline fee; adjusted sheet = total settled grid fee including adjustment, excluding emergency; do not add both sheets'};
await fs.writeFile(`${root}/outputs/q4/workbook_fill_${mode}.json`,JSON.stringify(report,null,2));console.log(report);
