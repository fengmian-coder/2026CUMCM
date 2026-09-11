import { signedArea } from './q1_plot_elements.mjs';
import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const root = path.resolve(import.meta.dirname, "..");
const outDir = path.join(root, "figures");
fs.mkdirSync(outDir, { recursive: true });

const C = {
  ink: "#263746", moss: "#466F87", lichen: "#98AF1E",
  mist: "#78B6C8", sand: "#E48578", paper: "#FFFFFF",
  gray: "#8F9188", grid: "#CFCFC7", white: "#FFFFFF"
};
const W = 1800, H = 980;
const FONT = "'Microsoft YaHei','Noto Sans CJK SC',sans-serif";
const baseStyle = `<style>text{font-family:${FONT};fill:${C.ink}}.tick{font-size:24px}.label{font-size:28px}.axis{stroke:${C.gray};stroke-width:2}.grid{stroke:${C.grid};stroke-width:1.5;opacity:.55}</style>`;
const wrap = body => `<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="${C.paper}"/>${baseStyle}${body}</svg>`;
const linePath = (xs, ys, x, y) => xs.length === 144 ? xs.map((v,i) => `${i ? "L" : "M"} ${x(i/6)} ${y(ys[i])} H ${x((i+1)/6)}`).join(" ") : xs.map((v,i) => `${i ? "L" : "M"} ${x(v)} ${y(ys[i])}`).join(" ");
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
  const m={l:165,r:165,t:170,b:160};
  const ymax=Math.ceil(Math.max(...load,...grid)/1000)*1000;
  const yticks=[]; for(let v=-5000;v<=ymax;v+=5000) yticks.push(v);
  const a=axes({m,xmin:0,xmax:24,ymin:-5200,ymax,xticks:[0,4,8,12,16,20,24],yticks,xlabel:"时间 / h",ylabel:"功率 / kW",yfmt:v=>v});
  const bars=signedArea(a,discharge.map((v,i)=>v-charge[i]),1/6,C.lichen,C.sand);
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="36" font-weight="600">微网日内功率优化调度</text>${a.frame}<line x1="${m.l}" y1="${a.y(0)}" x2="${W-m.r}" y2="${a.y(0)}" stroke="${C.ink}" stroke-width="2.2"/>${bars}<path d="${linePath(hour,load,a.x,a.y)}" fill="none" stroke="${C.ink}" stroke-width="4" stroke-dasharray="12 7"/><path d="${linePath(hour,pv,a.x,a.y)}" fill="none" stroke="#F2D98E" stroke-width="5"/><path d="${linePath(hour,grid,a.x,a.y)}" fill="none" stroke="${C.moss}" stroke-width="4"/>
  <g transform="translate(360 116)"><line x2="55" stroke="${C.ink}" stroke-width="4" stroke-dasharray="12 7"/><text x="68" y="8" font-size="23">小区负荷</text></g><g transform="translate(610 116)"><line x2="55" stroke="#F2D98E" stroke-width="5"/><text x="68" y="8" font-size="23">光伏功率</text></g><g transform="translate(860 116)"><line x2="55" stroke="${C.moss}" stroke-width="4"/><text x="68" y="8" font-size="23">外网购电</text></g><g transform="translate(1120 116)"><rect width="28" height="18" y="-10" fill="${C.lichen}"/><rect width="28" height="18" x="32" y="-10" fill="${C.sand}"/><text x="73" y="8" font-size="23">储能放电 / 充电</text></g>`;
  await save("q1_power_dispatch",wrap(body));
}

// 2) Price and battery operation with two axes.
{
  const m={l:165,r:165,t:170,b:160};
  const a=axes({m,xmin:0,xmax:24,ymin:-5200,ymax:5200,xticks:[0,4,8,12,16,20,24],yticks:[-5000,-2500,0,2500,5000],xlabel:"时间 / h",ylabel:"储能功率 / kW"});
  const pmin=.3,pmax=1.5, py=v=>m.t+(pmax-v)/(pmax-pmin)*(H-m.t-m.b);
  const bars=signedArea(a,discharge.map((v,i)=>v-charge[i]),1/6,C.lichen,C.sand);
  const rt=[.3,.6,.9,1.2,1.5].map(v=>`<text x="${W-m.r+22}" y="${py(v)+8}" class="tick">${v.toFixed(1)}</text>`).join("");
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="36" font-weight="600">分时电价与储能充放电策略</text>${a.frame}<line x1="${m.l}" y1="${a.y(0)}" x2="${W-m.r}" y2="${a.y(0)}" stroke="${C.ink}" stroke-width="2"/>${bars}<path d="${linePath(hour,price,a.x,py)}" fill="none" stroke="${C.moss}" stroke-width="5"/><line x1="${W-m.r}" y1="${m.t}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/>${rt}<text x="${W-42}" y="${m.t+a.ph/2}" text-anchor="middle" class="label" transform="rotate(90 ${W-42} ${m.t+a.ph/2})">电价 / (元/kWh)</text><g transform="translate(540 116)"><rect width="34" height="18" y="-10" fill="${C.sand}"/><text x="48" y="8" font-size="24">充电（负）</text></g><g transform="translate(790 116)"><rect width="34" height="18" y="-10" fill="${C.lichen}"/><text x="48" y="8" font-size="24">放电（正）</text></g><g transform="translate(1045 116)"><line x2="55" stroke="${C.moss}" stroke-width="5"/><text x="68" y="8" font-size="24">电价</text></g>`;
  await save("q1_price_storage",wrap(body));
}

// 3) Full-range dot plot and explicitly bounded detail panel.
{
 const vals=[noStorageCost,dpSummary.finest_total_cost_yuan,milpCost], colors=[C.lichen,C.sand,C.moss];
 const labels=['无储能','DP（5 kWh）','MILP'];
 const text=(x,y,t,size=24,anchor='middle')=>`<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${t}</text>`;
 const axis=(x0,w,lo,hi,ticks)=>{
  const x=v=>x0+(v-lo)/(hi-lo)*w;
  return {x,svg:ticks.map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="240" y2="780" class="grid"/>`+text(x(v),825,v)).join('')+`<line x1="${x0}" x2="${x0+w}" y1="780" y2="780" class="axis"/>`+text(x0+w/2,885,'全天购电费用 / 元',28)};
 };
 const left=axis(285,620,0,55000,[0,10000,20000,30000,40000,50000]);
 const right=axis(1170,460,35120,35160,[35120,35130,35140,35150,35160]);
 let body=text(900,62,'不同调度方案的购电费用对比',36)+text(595,160,'全范围',28)+text(1400,160,'局部放大：35120–35160 元',28)+left.svg+right.svg;
 vals.forEach((v,i)=>{const y=320+i*175;body+=text(250,y+8,labels[i],26,'end')+`<circle cx="${left.x(v)}" cy="${y}" r="11" fill="${colors[i]}"/>`+text(left.x(v),y-28,v.toFixed(2),25);});
 [1,2].forEach((i,j)=>{const y=430+j*220;body+=text(1140,y+8,labels[i],24,'end')+`<circle cx="${right.x(vals[i])}" cy="${y}" r="11" fill="${colors[i]}"/>`+text(right.x(vals[i]),y-28,vals[i].toFixed(2),25);});
 body+=text(1400,235,`费用差：${(vals[1]-vals[2]).toFixed(2)} 元`,25);
 await save('q1_cost_comparison',wrap(body));
}

// 4) DP convergence against the continuous MILP optimum.
{
  const conv=fs.readFileSync(path.join(root,"outputs/q1_dp/dp_convergence.csv"),"utf8").replace(/^\uFEFF/,"").trim().split(/\r?\n/);
  const cr=conv.slice(1).map(s=>s.split(","));
  const steps=cr.map(r=>+r[0]), errs=cr.map(r=>+r[18]*100);
  const m={l:165,r:165,t:170,b:160};
  const xs=steps, a=axes({m,xmin:Math.log10(220),xmax:Math.log10(4.5),ymin:0,ymax:3.5,xticks:[],yticks:[0,.5,1,1.5,2,2.5,3,3.5],xlabel:"储电量离散步长 / kWh（对数刻度）",ylabel:"相对 MILP 费用差 / %",yfmt:v=>v.toFixed(1)});
  const linearX=a.x; a.x=v=>linearX(Math.log10(v));
  const customX=steps.map((v,i)=>`<line x1="${a.x(steps[i])}" y1="${H-m.b}" x2="${a.x(steps[i])}" y2="${H-m.b+9}" class="axis"/><text x="${a.x(steps[i])}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}</text>`).join("");
  const pts=errs.map((v,i)=>`<circle cx="${a.x(steps[i])}" cy="${a.y(v)}" r="9" fill="${C.moss}" stroke="${C.paper}" stroke-width="3"/>`).join("");
  const body=`<text x="${W/2}" y="62" text-anchor="middle" font-size="36" font-weight="600">动态规划离散精度的收敛性</text>${a.frame}${customX}<path d="${linePath(xs,errs,a.x,a.y)}" fill="none" stroke="${C.moss}" stroke-width="5"/>${pts}`;
  await save("q1_dp_convergence",wrap(body));
}

console.log("Generated four question-1 figures in", outDir);

// Hourly contribution to savings; exact source values are retained in JSON.
{
  const savings=Array.from({length:24},(_,h)=>rows.slice(h*6,h*6+6).reduce((s,r)=>s+Number(r[2])*(Math.max(Number(r[3])-Number(r[4]),0)-Number(r[5])),0));
  const bound=Math.ceil(Math.max(...savings.map(Math.abs))/1000)*1000;
  const m={l:165,r:165,t:170,b:160};
  const a=axes({m,xmin:0,xmax:24,ymin:-bound,ymax:bound,xticks:[0,4,8,12,16,20,24],yticks:[-bound,-bound/2,0,bound/2,bound],xlabel:"时间 / h",ylabel:"每小时费用节省 / 元"});
  const bars=savings.map((v,h)=>`<rect x="${a.x(h)+6}" y="${Math.min(a.y(v),a.y(0))}" width="${a.pw/24-12}" height="${Math.abs(a.y(v)-a.y(0))}" fill="${v>=0?'#98AF1E':'#E48578'}"/>`).join('');
  await save('q1_hourly_savings',wrap(`<text x="900" y="62" text-anchor="middle" font-size="36" font-weight="600">储能经济收益的分时来源</text><text x="900" y="108" text-anchor="middle" font-size="24">无储能购电费用 − MILP 购电费用</text>${a.frame}${bars}<line x1="165" x2="1635" y1="${a.y(0)}" y2="${a.y(0)}" stroke="#263746" stroke-width="2"/>`));
  fs.writeFileSync(path.join(root,'outputs/q1_hourly_savings.json'),JSON.stringify({definition:'no-storage cost minus MILP cost',hourly_savings_yuan:savings},null,2));
}
