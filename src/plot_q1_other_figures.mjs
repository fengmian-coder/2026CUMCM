import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const root = path.resolve(import.meta.dirname, "..");
const outDir = path.join(root, "figures");
fs.mkdirSync(outDir, { recursive: true });

const C = {
  ink: "#2E2F23", moss: "#658873", lichen: "#B9C78D",
  mist: "#E7E3E4", sand: "#D2BFA5", paper: "#FAF9F5",
  gray: "#8F9188", grid: "#CFCFC7", white: "#FFFFFF"
};
const W = 1800, H = 980;
const FONT = "'Microsoft YaHei','Noto Sans CJK SC',sans-serif";
const baseStyle = `<style>text{font-family:${FONT};fill:${C.ink}}.tick{font-size:24px}.label{font-size:28px}.axis{stroke:${C.gray};stroke-width:2}.grid{stroke:${C.grid};stroke-width:1.5;opacity:.55}</style>`;
const wrap = body => `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="${C.paper}"/>${baseStyle}${body}</svg>`;
const linePath = (xs, ys, x, y) => xs.map((v,i) => `${i ? "L" : "M"} ${x(v).toFixed(2)} ${y(ys[i]).toFixed(2)}`).join(" ");
async function save(name, svg) {
  fs.writeFileSync(path.join(outDir, `${name}.svg`), svg, "utf8");
  await sharp(Buffer.from(svg)).png().toFile(path.join(outDir, `${name}.png`));
}
function axes({m, xmin, xmax, ymin, ymax, xticks, yticks, xlabel, ylabel, yfmt=v=>v}) {
  const pw=W-m.l-m.r, ph=H-m.t-m.b;
  const x=v=>m.l+(v-xmin)/(xmax-xmin)*pw, y=v=>m.t+(ymax-v)/(ymax-ymin)*ph;
  const yg=yticks.map(v=>`<line x1="${m.l}" y1="${y(v)}" x2="${W-m.r}" y2="${y(v)}" class="grid"/><text x="${m.l-22}" y="${y(v)+8}" text-anchor="end" class="tick">${yfmt(v)}</text>`).join("");
  const xg=xticks.map(v=>`<line x1="${x(v)}" y1="${H-m.b}" x2="${x(v)}" y2="${H-m.b+9}" class="axis"/><text x="${x(v)}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}</text>`).join("");
  const frame=`${yg}${xg}<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><text x="${W/2}" y="${H-m.b+88}" text-anchor="middle" class="label">${xlabel}</text><text x="52" y="${m.t+ph/2}" text-anchor="middle" class="label" transform="rotate(-90 52 ${m.t+ph/2})">${ylabel}</text>`;
  return {x,y,frame,pw,ph};
}

const csv = fs.readFileSync(path.join(root,"outputs/q1_milp_schedule.csv"),"utf8").replace(/^\uFEFF/,"");
const rows = csv.trim().split(/\r?\n/).slice(1).map(s=>s.split(","));
const hour = rows.map((_,i)=>(i+.5)/6);
const price=rows.map(r=>+r[2]), load=rows.map(r=>+r[3]*6), pv=rows.map(r=>+r[4]*6), grid=rows.map(r=>+r[5]*6), charge=rows.map(r=>+r[6]*6), discharge=rows.map(r=>+r[7]*6);
const milpCost = rows.reduce((sum,r)=>sum + Number(r[2])*Number(r[5]), 0);
const noStorageCost = rows.reduce((sum,r)=>sum + Number(r[2])*Math.max(Number(r[3])-Number(r[4]),0), 0);
const dpSummary = JSON.parse(fs.readFileSync(path.join(root,"outputs/q1_dp/dp_summary.json"),"utf8"));

// 1) Power dispatch: supply curves plus signed battery power bars.
{
  const m={l:155,r:80,t:120,b:190};
  const ymax=Math.ceil(Math.max(...load,...grid)/1000)*1000;
  const yticks=[]; for(let v=-5000;v<=ymax;v+=5000) yticks.push(v);
  const a=axes({m,xmin:0,xmax:24,ymin:-5200,ymax,xticks:[0,4,8,12,16,20,24],yticks,xlabel:"时间 / h",ylabel:"功率 / kW",yfmt:v=>v});
  const bars=hour.map((h,i)=>{const val=discharge[i]>1e-6?discharge[i]:-charge[i]; const yy=a.y(Math.max(val,0)), yy0=a.y(0); return `<rect x="${a.x(h)-3.4}" y="${Math.min(yy,a.y(val))}" width="6.8" height="${Math.abs(a.y(val)-yy0)}" fill="${val>=0?C.lichen:C.sand}" opacity=".8"/>`;}).join("");
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="39" font-weight="600">微网日内功率优化调度</text>${a.frame}<line x1="${m.l}" y1="${a.y(0)}" x2="${W-m.r}" y2="${a.y(0)}" stroke="${C.ink}" stroke-width="2.2"/>${bars}<path d="${linePath(hour,load,a.x,a.y)}" fill="none" stroke="${C.ink}" stroke-width="4"/><path d="${linePath(hour,pv,a.x,a.y)}" fill="none" stroke="${C.lichen}" stroke-width="4"/><path d="${linePath(hour,grid,a.x,a.y)}" fill="none" stroke="${C.moss}" stroke-width="4"/>
  <g transform="translate(360 ${H-85})"><line x2="55" stroke="${C.ink}" stroke-width="4"/><text x="68" y="8" font-size="23">小区负荷</text></g><g transform="translate(610 ${H-85})"><line x2="55" stroke="${C.lichen}" stroke-width="4"/><text x="68" y="8" font-size="23">光伏功率</text></g><g transform="translate(860 ${H-85})"><line x2="55" stroke="${C.moss}" stroke-width="4"/><text x="68" y="8" font-size="23">外网购电</text></g><g transform="translate(1120 ${H-85})"><rect width="28" height="18" y="-10" fill="${C.lichen}"/><rect width="28" height="18" x="32" y="-10" fill="${C.sand}"/><text x="73" y="8" font-size="23">储能放电 / 充电</text></g>`;
  await save("q1_power_dispatch",wrap(body));
}

// 2) Price and battery operation with two axes.
{
  const m={l:150,r:165,t:120,b:180};
  const a=axes({m,xmin:0,xmax:24,ymin:-5200,ymax:5200,xticks:[0,4,8,12,16,20,24],yticks:[-5000,-2500,0,2500,5000],xlabel:"时间 / h",ylabel:"储能功率 / kW"});
  const pmin=.3,pmax=1.5, py=v=>m.t+(pmax-v)/(pmax-pmin)*(H-m.t-m.b);
  const bars=hour.map((h,i)=>{const v=discharge[i]>1e-6?discharge[i]:-charge[i];return `<rect x="${a.x(h)-4}" y="${Math.min(a.y(v),a.y(0))}" width="8" height="${Math.abs(a.y(v)-a.y(0))}" rx="1" fill="${v>=0?C.lichen:C.sand}" opacity=".88"/>`;}).join("");
  const rt=[.3,.6,.9,1.2,1.5].map(v=>`<text x="${W-m.r+22}" y="${py(v)+8}" class="tick">${v.toFixed(1)}</text>`).join("");
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="39" font-weight="600">分时电价与储能充放电策略</text>${a.frame}<line x1="${m.l}" y1="${a.y(0)}" x2="${W-m.r}" y2="${a.y(0)}" stroke="${C.ink}" stroke-width="2"/>${bars}<path d="${linePath(hour,price,a.x,py)}" fill="none" stroke="${C.moss}" stroke-width="5"/><line x1="${W-m.r}" y1="${m.t}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/>${rt}<text x="${W-42}" y="${m.t+a.ph/2}" text-anchor="middle" class="label" transform="rotate(90 ${W-42} ${m.t+a.ph/2})">电价 /（元·kWh⁻¹）</text><g transform="translate(540 ${H-72})"><rect width="34" height="18" y="-10" fill="${C.sand}"/><text x="48" y="8" font-size="24">充电（负）</text></g><g transform="translate(790 ${H-72})"><rect width="34" height="18" y="-10" fill="${C.lichen}"/><text x="48" y="8" font-size="24">放电（正）</text></g><g transform="translate(1045 ${H-72})"><line x2="55" stroke="${C.moss}" stroke-width="5"/><text x="68" y="8" font-size="24">电价</text></g>`;
  await save("q1_price_storage",wrap(body));
}

// 3) Cost comparison.
{
  const m={l:170,r:90,t:145,b:200}, vals=[noStorageCost,dpSummary.finest_total_cost_yuan,milpCost], labels=["无储能","动态规划（5 kWh）","MILP优化"], colors=[C.mist,C.sand,C.moss];
  const a=axes({m,xmin:0,xmax:3,ymin:0,ymax:52000,xticks:[],yticks:[0,10000,20000,30000,40000,50000],xlabel:"",ylabel:"全天购电费用 / 元",yfmt:v=>v.toLocaleString("zh-CN")});
  const bars=vals.map((v,i)=>{const cx=a.x(i+.5),bw=250;return `<rect x="${cx-bw/2}" y="${a.y(v)}" width="${bw}" height="${a.y(0)-a.y(v)}" rx="10" fill="${colors[i]}"/><text x="${cx}" y="${a.y(v)-22}" text-anchor="middle" font-size="28" font-weight="600">${v.toFixed(2)}</text><text x="${cx}" y="${H-m.b+48}" text-anchor="middle" font-size="28">${labels[i]}</text>`;}).join("");
  const saving=noStorageCost-milpCost, savingRate=saving/noStorageCost*100, dpGap=dpSummary.finest_total_cost_yuan-milpCost;
  const body=`<text x="${W/2}" y="52" text-anchor="middle" font-size="39" font-weight="600">不同储能调度方案的购电费用对比</text><text x="${W/2}" y="101" text-anchor="middle" font-size="25" fill="${C.moss}">MILP 优化较无储能方案节省 ${saving.toFixed(2)} 元（${savingRate.toFixed(2)}%）</text>${a.frame}${bars}<text x="${W/2}" y="${H-42}" text-anchor="middle" font-size="21" fill="#66685F">动态规划采用 5 kWh 储电量网格，费用与 MILP 连续最优解相差 ${dpGap.toFixed(2)} 元。</text>`;
  await save("q1_cost_comparison",wrap(body));
}

// 4) DP convergence against the continuous MILP optimum.
{
  const conv=fs.readFileSync(path.join(root,"outputs/q1_dp/dp_convergence.csv"),"utf8").replace(/^\uFEFF/,"").trim().split(/\r?\n/);
  const cr=conv.slice(1).map(s=>s.split(","));
  const steps=cr.map(r=>+r[0]), errs=cr.map(r=>+r[18]*100);
  const m={l:160,r:80,t:120,b:185};
  const xs=steps.map((_,i)=>i), a=axes({m,xmin:0,xmax:5,ymin:0,ymax:3.5,xticks:[],yticks:[0,.5,1,1.5,2,2.5,3,3.5],xlabel:"储电量离散步长 / kWh",ylabel:"相对 MILP 费用误差 / %",yfmt:v=>v.toFixed(1)});
  const customX=steps.map((v,i)=>`<line x1="${a.x(i)}" y1="${H-m.b}" x2="${a.x(i)}" y2="${H-m.b+9}" class="axis"/><text x="${a.x(i)}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}</text>`).join("");
  const pts=errs.map((v,i)=>`<circle cx="${a.x(i)}" cy="${a.y(v)}" r="9" fill="${C.moss}" stroke="${C.paper}" stroke-width="3"/><text x="${a.x(i)}" y="${a.y(v)-22}" text-anchor="middle" font-size="22">${v.toFixed(3)}%</text>`).join("");
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="39" font-weight="600">动态规划离散精度的收敛性</text>${a.frame}${customX}<path d="${linePath(xs,errs,a.x,a.y)}" fill="none" stroke="${C.moss}" stroke-width="5"/>${pts}<text x="${W/2}" y="${H-48}" text-anchor="middle" font-size="22" fill="#66685F">随着状态网格细化，动态规划结果稳定逼近连续 MILP 最优解。</text>`;
  await save("q1_dp_convergence",wrap(body));
}

console.log("Generated four question-1 figures in", outDir);
