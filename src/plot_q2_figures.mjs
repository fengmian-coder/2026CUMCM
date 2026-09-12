import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const root = path.resolve(import.meta.dirname, "..");
const outDir = path.join(root, "figures");
fs.mkdirSync(outDir, { recursive: true });

const C = {
  ink: "#263746", blue: "#466F87", cyan: "#78B6C8",
  yellow: "#F2D98E", coral: "#E48578", green: "#98AF1E",
  gray: "#8F9188", grid: "#CFCFC7", paper: "#FFFFFF",
};
const W = 1800, H = 980;
const FONT = "'Microsoft YaHei','Noto Sans CJK SC',sans-serif";
const style = `<style>text{font-family:${FONT};fill:${C.ink}}.tick{font-size:22px}.label{font-size:27px}.axis{stroke:${C.gray};stroke-width:2}.grid{stroke:${C.grid};stroke-width:1.4;opacity:.55}</style>`;
const wrap = body => `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="${C.paper}"/>${style}${body}</svg>`;

async function save(name, body) {
  const svg = wrap(body);
  fs.writeFileSync(path.join(outDir, `${name}.svg`), svg, "utf8");
  await sharp(Buffer.from(svg)).png().toFile(path.join(outDir, `${name}.png`));
}
function parseCsvLine(line) {
  const out=[]; let value="", quoted=false;
  for(let i=0;i<line.length;i++){
    const c=line[i];
    if(c==='"'){ if(quoted&&line[i+1]==='"'){value+='"';i++;} else quoted=!quoted; }
    else if(c===','&&!quoted){out.push(value);value="";} else value+=c;
  }
  out.push(value); return out;
}
function readCsv(file) {
  return fs.readFileSync(file,"utf8").replace(/^\uFEFF/,"").trim().split(/\r?\n/).map(parseCsvLine);
}
const linePath=(values,x,y)=>values.map((v,i)=>`${i?"L":"M"} ${x(i)} ${y(v)}`).join(" ");
const stepPath=(values,x,y)=>`M ${x(0)} ${y(values[0])} `+values.map((v,i)=>`L ${x(i+1)} ${y(v)}${i<values.length-1?` L ${x(i+1)} ${y(values[i+1])}`:""}`).join(" ");
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const mix=(a,b,t)=>{
  const pa=a.match(/[0-9a-f]{2}/gi).map(v=>parseInt(v,16));
  const pb=b.match(/[0-9a-f]{2}/gi).map(v=>parseInt(v,16));
  return `rgb(${pa.map((v,i)=>Math.round(v+(pb[i]-v)*t)).join(",")})`;
};

const schedule=readCsv(path.join(root,"outputs/q2/q2_schedule.csv"));
const byDate=new Map();
for(const row of schedule.slice(1)){
  if(!byDate.has(row[0]))byDate.set(row[0],[]);
  byDate.get(row[0]).push(row);
}

// Four dates specified by the problem.
{
  const dates=["2025-03-20","2025-06-21","2025-09-23","2025-12-21"];
  const panels=[{x:145,y:185},{x:945,y:185},{x:145,y:555},{x:945,y:555}];
  const pw=690,ph=245;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">指定日期微网调度结果</text>`;
  body+=`<g transform="translate(230 112)"><line x2="44" stroke="${C.ink}" stroke-width="4"/><text x="56" y="7" font-size="21">实际净负荷</text></g><g transform="translate(515 112)"><line x2="44" stroke="${C.blue}" stroke-width="4"/><text x="56" y="7" font-size="21">计划购电</text></g><g transform="translate(790 112)"><line x2="44" stroke="${C.green}" stroke-width="4"/><text x="56" y="7" font-size="21">储能净放电</text></g><g transform="translate(1115 112)"><rect y="-12" width="40" height="18" fill="${C.coral}" opacity=".72"/><text x="53" y="7" font-size="21">紧急购电</text></g>`;
  dates.forEach((date,pi)=>{
    const r=byDate.get(date);
    const net=r.map(v=>+v[6]-+v[7]);
    const grid=r.map(v=>+v[8]*6);
    const battery=r.map(v=>(+v[10]-+v[9])*6);
    const emergency=r.map(v=>+v[11]*6);
    const ymin=Math.floor(Math.min(-1000,...battery,...net)/3000)*3000;
    const ymax=Math.ceil(Math.max(...net,...grid,...emergency)/3000)*3000;
    const p=panels[pi],x=i=>p.x+i/144*pw,y=v=>p.y+(ymax-v)/(ymax-ymin)*ph;
    for(let v=ymin;v<=ymax;v+=6000)body+=`<line x1="${p.x}" y1="${y(v)}" x2="${p.x+pw}" y2="${y(v)}" class="grid"/><text x="${p.x-16}" y="${y(v)+7}" text-anchor="end" font-size="18">${v}</text>`;
    [0,6,12,18,24].forEach(h=>{const xx=p.x+h/24*pw;body+=`<line x1="${xx}" y1="${p.y+ph}" x2="${xx}" y2="${p.y+ph+7}" class="axis"/><text x="${xx}" y="${p.y+ph+30}" text-anchor="middle" font-size="18">${h}</text>`;});
    const area=`M ${x(0)} ${y(0)} `+emergency.map((v,i)=>`L ${x(i)} ${y(v)}`).join(" ")+` L ${x(143)} ${y(0)} Z`;
    body+=`<text x="${p.x+pw/2}" y="${p.y-25}" text-anchor="middle" font-size="25" font-weight="600">${date}</text><line x1="${p.x}" y1="${p.y+ph}" x2="${p.x+pw}" y2="${p.y+ph}" class="axis"/><line x1="${p.x}" y1="${p.y}" x2="${p.x}" y2="${p.y+ph}" class="axis"/><path d="${area}" fill="${C.coral}" opacity=".58"/><path d="${stepPath(net,x,y)}" fill="none" stroke="${C.ink}" stroke-width="3.4"/><path d="${stepPath(grid,x,y)}" fill="none" stroke="${C.blue}" stroke-width="3.4"/><path d="${stepPath(battery,x,y)}" fill="none" stroke="${C.green}" stroke-width="3.1"/>`;
  });
  body+=`<text x="43" y="500" text-anchor="middle" class="label" transform="rotate(-90 43 500)">功率 / kW</text><text x="900" y="950" text-anchor="middle" class="label">时间 / h</text>`;
  await save("q2_specified_day_dispatch",body);
}

// Monthly total cost and emergency volume.
{
  const months=Array.from({length:11},(_,i)=>i+2);
  const monthly=months.map(m=>({m,plan:0,emgCost:0,emg:0}));
  for(const [date,r] of byDate){
    const item=monthly[Number(date.slice(5,7))-2];
    item.plan+=r.reduce((s,v)=>s+(+v[3])*(+v[8]),0);
    item.emgCost+=r.reduce((s,v)=>s+5*(+v[3])*(+v[11]),0);
    item.emg+=r.reduce((s,v)=>s+(+v[11]),0);
  }
  const m={l:165,r:175,t:165,b:145},pw=W-m.l-m.r,ph=H-m.t-m.b;
  const total=monthly.map(v=>(v.plan+v.emgCost)/10000),emg=monthly.map(v=>v.emg/10000);
  const ymax=Math.ceil(Math.max(...total)/20)*20,rmax=Math.ceil(Math.max(...emg));
  const x=i=>m.l+i/(months.length-1)*pw,y=v=>m.t+(ymax-v)/ymax*ph,yr=v=>m.t+(rmax-v)/rmax*ph;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">月度购电费用与紧急购电量</text>`;
  for(let v=0;v<=ymax;v+=20)body+=`<line x1="${m.l}" y1="${y(v)}" x2="${W-m.r}" y2="${y(v)}" class="grid"/><text x="${m.l-20}" y="${y(v)+8}" text-anchor="end" class="tick">${v}</text>`;
  months.forEach((v,i)=>body+=`<text x="${x(i)}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}月</text>`);
  for(let v=0;v<=rmax;v++)body+=`<text x="${W-m.r+20}" y="${yr(v)+8}" class="tick">${v}</text>`;
  body+=`<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><line x1="${W-m.r}" y1="${m.t}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><path d="${linePath(total,x,y)}" fill="none" stroke="${C.blue}" stroke-width="5"/>${total.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v)}" r="8" fill="${C.blue}" stroke="white" stroke-width="3"/>`).join("")}<path d="${linePath(emg,x,yr)}" fill="none" stroke="${C.coral}" stroke-width="5"/>${emg.map((v,i)=>`<circle cx="${x(i)}" cy="${yr(v)}" r="8" fill="${C.coral}" stroke="white" stroke-width="3"/>`).join("")}<text x="52" y="500" text-anchor="middle" class="label" transform="rotate(-90 52 500)">购电费用 / 万元</text><text x="1755" y="500" text-anchor="middle" class="label" transform="rotate(90 1755 500)">紧急购电量 / 万 kWh</text><g transform="translate(585 112)"><line x2="50" stroke="${C.blue}" stroke-width="5"/><text x="64" y="8" font-size="23">总购电费用</text></g><g transform="translate(970 112)"><line x2="50" stroke="${C.coral}" stroke-width="5"/><text x="64" y="8" font-size="23">紧急购电量</text></g>`;
  await save("q2_monthly_cost_emergency",body);
}

// Cost comparison without bars.
{
  const b=JSON.parse(fs.readFileSync(path.join(root,"outputs/q2/benchmark_summary.json"),"utf8"));
  const values=[b.perfect_information_storage_reference.total_cost_yuan,b.proposed_stochastic_storage.total_cost_yuan,b.no_storage_same_information.total_cost_yuan].map(v=>v/10000);
  const labels=["理想信息储能参照","本文随机优化方案","无储能同信息方案"],colors=[C.green,C.blue,C.coral];
  const x0=390,x1=1600,y0=300,dy=205,xmin=1000,xmax=2000,x=v=>x0+(v-xmin)/(xmax-xmin)*(x1-x0);
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">不同信息与储能条件下的费用比较</text>`;
  for(let v=1000;v<=2000;v+=200)body+=`<line x1="${x(v)}" y1="190" x2="${x(v)}" y2="790" class="grid"/><text x="${x(v)}" y="842" text-anchor="middle" class="tick">${v}</text>`;
  values.forEach((v,i)=>{const y=y0+i*dy;body+=`<text x="${x0-35}" y="${y+8}" text-anchor="end" font-size="27">${labels[i]}</text><line x1="${x0}" y1="${y}" x2="${x(v)}" y2="${y}" stroke="${colors[i]}" stroke-width="5" opacity=".8"/><circle cx="${x(v)}" cy="${y}" r="14" fill="${colors[i]}" stroke="white" stroke-width="4"/><text x="${x(v)+24}" y="${y-22}" font-size="25" font-weight="600">${v.toFixed(2)}</text>`;});
  body+=`<line x1="${x0}" y1="790" x2="${x1}" y2="790" class="axis"/><text x="995" y="915" text-anchor="middle" class="label">2025年2—12月总购电费用 / 万元</text><path d="M ${x(values[1])} 690 L ${x(values[2])} 690" stroke="${C.green}" stroke-width="4"/><path d="M ${x(values[1])} 678 L ${x(values[1])} 702 M ${x(values[2])} 678 L ${x(values[2])} 702" stroke="${C.green}" stroke-width="4"/><text x="${(x(values[1])+x(values[2]))/2}" y="665" text-anchor="middle" font-size="25">节省 ${(values[2]-values[1]).toFixed(2)} 万元</text>`;
  await save("q2_model_cost_comparison",body);
}

// Cost-risk frontier.
{
  const s=readCsv(path.join(root,"outputs/q2/sensitivity/sensitivity_summary.csv"));
  const map=new Map(s.slice(1).map(r=>[r[0],r]));
  const keys=["risk_0","risk_005","risk_010","risk_020"],lambdas=[0,.05,.10,.20];
  const pts=keys.map(k=>({cost:+map.get(k)[3]/10000,emg:+map.get(k)[4]/10000}));
  const m={l:190,r:150,t:175,b:155},pw=W-m.l-m.r,ph=H-m.t-m.b;
  const xmin=15,xmax=28,ymin=1460,ymax=1510,x=v=>m.l+(v-xmin)/(xmax-xmin)*pw,y=v=>m.t+(ymax-v)/(ymax-ymin)*ph;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">风险权重下的费用—紧急购电权衡</text>`;
  for(let v=1460;v<=1510;v+=10)body+=`<line x1="${m.l}" y1="${y(v)}" x2="${W-m.r}" y2="${y(v)}" class="grid"/><text x="${m.l-22}" y="${y(v)+8}" text-anchor="end" class="tick">${v}</text>`;
  for(let v=16;v<=28;v+=2)body+=`<text x="${x(v)}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}</text>`;
  body+=`<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><path d="${pts.map((p,i)=>`${i?"L":"M"} ${x(p.emg)} ${y(p.cost)}`).join(" ")}" fill="none" stroke="${C.blue}" stroke-width="5"/>`;
  pts.forEach((p,i)=>{const chosen=i===1;body+=`<circle cx="${x(p.emg)}" cy="${y(p.cost)}" r="${chosen?15:11}" fill="${chosen?C.green:C.blue}" stroke="white" stroke-width="4"/><text x="${x(p.emg)+(i<2?18:-18)}" y="${y(p.cost)-22}" text-anchor="${i<2?'start':'end'}" font-size="24" font-weight="${chosen?'600':'400'}">λ = ${lambdas[i].toFixed(i?2:0)}</text>`;});
  body+=`<text x="900" y="930" text-anchor="middle" class="label">紧急购电量 / 万 kWh</text><text x="55" y="500" text-anchor="middle" class="label" transform="rotate(-90 55 500)">总购电费用 / 万元</text>`;
  await save("q2_risk_cost_frontier",body);
}

// Emergency-purchase heat map: date by time of day.
{
  const rows=[...byDate.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  const values=rows.map(([,r])=>r.map(v=>+v[11]));
  const positive=values.flat().filter(v=>v>1e-10).sort((a,b)=>a-b);
  const cap=positive.at(-1) || 1;
  const m={l:175,r:205,t:145,b:135},pw=W-m.l-m.r,ph=H-m.t-m.b;
  const cw=pw/144,ch=ph/rows.length;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">2025年2—12月紧急购电时空分布</text>`;
  values.forEach((day,di)=>day.forEach((v,ti)=>{
    const q=clamp(Math.log1p(v)/Math.log1p(cap),0,1);
    const fill=v<=1e-10?"#F4F3EF":mix(C.yellow,C.coral,q);
    body+=`<rect x="${m.l+ti*cw}" y="${m.t+di*ch}" width="${cw+.2}" height="${ch+.2}" fill="${fill}"/>`;
  }));
  [0,4,8,12,16,20,24].forEach(h=>{const xx=m.l+h/24*pw;body+=`<line x1="${xx}" y1="${H-m.b}" x2="${xx}" y2="${H-m.b+8}" class="axis"/><text x="${xx}" y="${H-m.b+42}" text-anchor="middle" class="tick">${h}</text>`;});
  const monthTicks=["2025-02-01","2025-04-01","2025-06-01","2025-08-01","2025-10-01","2025-12-01"];
  monthTicks.forEach(d=>{const i=rows.findIndex(v=>v[0]===d);if(i>=0){const yy=m.t+i*ch;body+=`<line x1="${m.l-8}" y1="${yy}" x2="${m.l}" y2="${yy}" class="axis"/><text x="${m.l-18}" y="${yy+7}" text-anchor="end" class="tick">${d.slice(5,7)}月</text>`;}});
  body+=`<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><text x="${m.l+pw/2}" y="930" text-anchor="middle" class="label">时间 / h</text>`;
  const lx=W-145,ly=m.t+40,lh=ph-80,steps=90;
  for(let i=0;i<steps;i++)body+=`<rect x="${lx}" y="${ly+i*lh/steps}" width="26" height="${lh/steps+1}" fill="${mix(C.coral,C.yellow,i/(steps-1))}"/>`;
  body+=`<text x="${lx+13}" y="${ly-18}" text-anchor="middle" font-size="21">${cap.toFixed(1)}</text><text x="${lx+13}" y="${ly+lh+34}" text-anchor="middle" font-size="21">0</text><text x="${lx+72}" y="${ly+lh/2}" text-anchor="middle" font-size="23" transform="rotate(90 ${lx+72} ${ly+lh/2})">紧急购电量 / kWh（log(1+q)色阶）</text>`;
  await save("q2_emergency_heatmap",body);
}

// Annual state-of-charge heat map.
{
  const rows=[...byDate.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  const values=rows.map(([,r])=>r.map(v=>100*(+v[13])/12000));
  const m={l:175,r:205,t:145,b:135},pw=W-m.l-m.r,ph=H-m.t-m.b,cw=pw/144,ch=ph/rows.length;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">2025年2—12月储能荷电状态分布</text>`;
  values.forEach((day,di)=>day.forEach((v,ti)=>{
    const q=clamp((v-10)/80,0,1);
    body+=`<rect x="${m.l+ti*cw}" y="${m.t+di*ch}" width="${cw+.2}" height="${ch+.2}" fill="${mix(C.yellow,C.blue,q)}"/>`;
  }));
  [0,4,8,12,16,20,24].forEach(h=>{const xx=m.l+h/24*pw;body+=`<line x1="${xx}" y1="${H-m.b}" x2="${xx}" y2="${H-m.b+8}" class="axis"/><text x="${xx}" y="${H-m.b+42}" text-anchor="middle" class="tick">${h}</text>`;});
  ["2025-02-01","2025-04-01","2025-06-01","2025-08-01","2025-10-01","2025-12-01"].forEach(d=>{const i=rows.findIndex(v=>v[0]===d);if(i>=0){const yy=m.t+i*ch;body+=`<line x1="${m.l-8}" y1="${yy}" x2="${m.l}" y2="${yy}" class="axis"/><text x="${m.l-18}" y="${yy+7}" text-anchor="end" class="tick">${d.slice(5,7)}月</text>`;}});
  body+=`<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><text x="${m.l+pw/2}" y="930" text-anchor="middle" class="label">时间 / h</text>`;
  const lx=W-145,ly=m.t+40,lh=ph-80,steps=90;
  for(let i=0;i<steps;i++)body+=`<rect x="${lx}" y="${ly+i*lh/steps}" width="26" height="${lh/steps+1}" fill="${mix(C.blue,C.yellow,i/(steps-1))}"/>`;
  body+=`<text x="${lx+13}" y="${ly-18}" text-anchor="middle" font-size="21">90%</text><text x="${lx+13}" y="${ly+lh+34}" text-anchor="middle" font-size="21">10%</text><text x="${lx+72}" y="${ly+lh/2}" text-anchor="middle" font-size="23" transform="rotate(90 ${lx+72} ${ly+lh/2})">SOC / %</text>`;
  await save("q2_soc_heatmap",body);
}

// Forecast interval, actual net load, and resulting day-ahead purchase.
{
  const figureData=JSON.parse(fs.readFileSync(path.join(root,"outputs/q2/q2_figure_data.json"),"utf8"));
  const panels=[{x:145,y:185},{x:945,y:185},{x:145,y:555},{x:945,y:555}],pw=690,ph=245;
  let body=`<text x="900" y="58" text-anchor="middle" font-size="36" font-weight="600">净负荷场景区间与日前购电决策</text>`;
  body+=`<g transform="translate(245 112)"><rect y="-13" width="42" height="19" fill="${C.yellow}" opacity=".65"/><text x="55" y="7" font-size="21">场景10%—90%区间</text></g><g transform="translate(630 112)"><line x2="44" stroke="${C.cyan}" stroke-width="4"/><text x="56" y="7" font-size="21">点预测</text></g><g transform="translate(875 112)"><line x2="44" stroke="${C.ink}" stroke-width="4"/><text x="56" y="7" font-size="21">实际净负荷</text></g><g transform="translate(1215 112)"><line x2="44" stroke="${C.blue}" stroke-width="4" stroke-dasharray="11 7"/><text x="56" y="7" font-size="21">计划购电</text></g>`;
  figureData.panels.forEach((r,pi)=>{
    const all=[...r.scenario_p10_net_kw,...r.scenario_p90_net_kw,...r.actual_net_kw,...r.planned_grid_kw];
    const ymin=Math.floor(Math.min(...all,0)/3000)*3000,ymax=Math.ceil(Math.max(...all)/3000)*3000;
    const p=panels[pi],x=i=>p.x+(i+1)/145*pw,y=v=>p.y+(ymax-v)/(ymax-ymin)*ph;
    for(let v=ymin;v<=ymax;v+=3000)body+=`<line x1="${p.x}" y1="${y(v)}" x2="${p.x+pw}" y2="${y(v)}" class="grid"/><text x="${p.x-16}" y="${y(v)+7}" text-anchor="end" font-size="18">${v}</text>`;
    [0,6,12,18,24].forEach(h=>{const xx=p.x+h/(145/6)*pw;body+=`<line x1="${xx}" y1="${p.y+ph}" x2="${xx}" y2="${p.y+ph+7}" class="axis"/><text x="${xx}" y="${p.y+ph+30}" text-anchor="middle" font-size="18">${h}</text>`;});
    const band=`M ${r.scenario_p90_net_kw.map((v,i)=>`${x(i)} ${y(v)}`).join(" L ")} L ${r.scenario_p10_net_kw.map((v,i)=>`${x(143-i)} ${y(r.scenario_p10_net_kw[143-i])}`).join(" L ")} Z`;
    body+=`<text x="${p.x+pw/2}" y="${p.y-25}" text-anchor="middle" font-size="25" font-weight="600">${r.date}</text><line x1="${p.x}" y1="${p.y+ph}" x2="${p.x+pw}" y2="${p.y+ph}" class="axis"/><line x1="${p.x}" y1="${p.y}" x2="${p.x}" y2="${p.y+ph}" class="axis"/><path d="${band}" fill="${C.yellow}" opacity=".55"/><path d="${linePath(r.forecast_net_kw,x,y)}" fill="none" stroke="${C.cyan}" stroke-width="3.2"/><path d="${linePath(r.actual_net_kw,x,y)}" fill="none" stroke="${C.ink}" stroke-width="3.4"/><path d="${stepPath(r.planned_grid_kw,x,y)}" fill="none" stroke="${C.blue}" stroke-width="3.2" stroke-dasharray="11 7"/>`;
  });
  body+=`<text x="43" y="500" text-anchor="middle" class="label" transform="rotate(-90 43 500)">功率 / kW</text><text x="900" y="950" text-anchor="middle" class="label">时间 / h（24:00为次日零点，计划止于24:10）</text>`;
  await save("q2_forecast_interval_dispatch",body);
}

console.log("Generated seven question-2 figures in",outDir);
