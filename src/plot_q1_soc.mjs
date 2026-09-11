import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

const root = path.resolve(import.meta.dirname, "..");
const csv = fs.readFileSync(path.join(root, "outputs/q1_milp_schedule.csv"), "utf8").replace(/^\uFEFF/, "");
const rows = csv.trim().split(/\r?\n/).slice(1).map(line => line.split(","));
const energy = [Number(rows[0][9]), ...rows.map(r => Number(r[10]))];

const W = 1800, H = 980;
const m = {l: 165, r: 165, t: 170, b: 260};
const pw = W - m.l - m.r, ph = H - m.t - m.b;
const x = h => m.l + h / 24 * pw;
const y = e => m.t + (12000 - e) / 12000 * ph;
const C = {ink:"#263746", moss:"#466F87", lichen:"#98AF1E", mist:"#78B6C8", sand:"#E48578", paper:"#FFFFFF"};
const esc = s => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;");

let step = `M ${x(0)} ${y(energy[0])}`;
for (let i = 1; i < energy.length; i++) step += ` L ${x(i/6)} ${y(energy[i])}`;
let area = `M ${x(0)} ${y(1200)} L ${x(0)} ${y(energy[0])}`;
for (let i = 1; i < energy.length; i++) area += ` L ${x(i/6)} ${y(energy[i])}`;
area += ` L ${x(24)} ${y(1200)} Z`;

const grid = Array.from({length:7}, (_,i) => i*2000).map(v =>
  `<line x1="${m.l}" y1="${y(v)}" x2="${W-m.r}" y2="${y(v)}" class="grid"/><text x="${m.l-25}" y="${y(v)+8}" text-anchor="end" class="tick">${v}</text>`).join("");
const xticks = Array.from({length:7}, (_,i) => i*4).map(v =>
  `<line x1="${x(v)}" y1="${H-m.b}" x2="${x(v)}" y2="${H-m.b+9}" class="axis"/><text x="${x(v)}" y="${H-m.b+42}" text-anchor="middle" class="tick">${v}</text>`).join("");
const rticks = Array.from({length:6}, (_,i) => i*20).map(v =>
  `<text x="${W-m.r+25}" y="${y(v*120)+8}" class="tick">${v}</text>`).join("");

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<rect width="100%" height="100%" fill="${C.paper}"/>
<style>
text{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:${C.ink}} .tick{font-size:24px}.axis{stroke:#8F9188;stroke-width:2}.grid{stroke:#CFCFC7;stroke-width:1.5;opacity:.58}
</style>
<text x="${W/2}" y="62" text-anchor="middle" font-size="36" font-weight="600">储能系统日内储电量变化</text>
<rect x="${m.l}" y="${y(10800)}" width="${pw}" height="${y(1200)-y(10800)}" fill="${C.mist}" opacity=".38"/>
${grid}${rticks}
<line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" class="axis"/><line x1="${W-m.r}" y1="${m.t}" x2="${W-m.r}" y2="${H-m.b}" class="axis"/>
<path d="${area}" fill="${C.moss}" opacity=".18"/><path d="${step}" fill="none" stroke="${C.moss}" stroke-width="5" stroke-linejoin="round"/>
<line x1="${m.l}" y1="${y(10800)}" x2="${W-m.r}" y2="${y(10800)}" stroke="${C.lichen}" stroke-width="4" stroke-dasharray="14 9"/>
<line x1="${m.l}" y1="${y(1200)}" x2="${W-m.r}" y2="${y(1200)}" stroke="${C.sand}" stroke-width="4" stroke-dasharray="14 9"/>
<circle cx="${x(0)}" cy="${y(6000)}" r="8" fill="${C.ink}" stroke="${C.paper}" stroke-width="3"/><circle cx="${x(24)}" cy="${y(6000)}" r="8" fill="${C.ink}" stroke="${C.paper}" stroke-width="3"/>
<text x="${x(.7)}" y="${y(6000)-28}" font-size="24">初始 6000 kWh</text><text x="${x(20.2)}" y="${y(6000)-28}" font-size="24">终止 6000 kWh</text>
<text x="${W/2}" y="935" text-anchor="middle" font-size="28">时间 / h</text>
<text x="52" y="${m.t+ph/2}" text-anchor="middle" font-size="28" transform="rotate(-90 52 ${m.t+ph/2})">储能电量 / kWh</text>
<text x="${W-42}" y="${m.t+ph/2}" text-anchor="middle" font-size="28" transform="rotate(90 ${W-42} ${m.t+ph/2})">荷电状态 SOC / %</text>
<g transform="translate(430 116)"><line x1="0" y1="0" x2="62" y2="0" stroke="${C.moss}" stroke-width="5"/><text x="75" y="8" font-size="24">储能电量</text></g>
<g transform="translate(755 116)"><line x1="0" y1="0" x2="62" y2="0" stroke="${C.lichen}" stroke-width="4" stroke-dasharray="14 9"/><text x="75" y="8" font-size="24">储电量上限（90%）</text></g>
<g transform="translate(1175 116)"><line x1="0" y1="0" x2="62" y2="0" stroke="${C.sand}" stroke-width="4" stroke-dasharray="14 9"/><text x="75" y="8" font-size="24">储电量下限（10%）</text></g>


<text x="${m.l-25}" y="801" text-anchor="end" font-size="24">运行状态</text>
${rows.map((r,i)=>`<rect x="${x(i/6)}" y="775" width="${pw/144}" height="38" fill="${Number(r[6])>1e-6?C.sand:Number(r[7])>1e-6?C.lichen:'#E7E3E4'}"/>`).join('')}
${Array.from({length:7},(_,i)=>i*4).map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="813" y2="822" class="axis"/><text x="${x(v)}" y="850" text-anchor="middle" class="tick">${v}</text>`).join('')}
<g font-size="23"><rect x="560" y="877" width="26" height="18" fill="${C.sand}"/><text x="600" y="894">充电</text><rect x="820" y="877" width="26" height="18" fill="${C.lichen}"/><text x="860" y="894">放电</text><rect x="1080" y="877" width="26" height="18" fill="#E7E3E4"/><text x="1120" y="894">空闲</text></g>

</svg>`;

const out = path.join(root, "figures");
fs.mkdirSync(out, {recursive:true});
const svgPath = path.join(out, "q1_soc_timeline.svg");
fs.writeFileSync(svgPath, svg, "utf8");
await sharp(Buffer.from(svg)).png().toFile(path.join(out, "q1_soc_timeline.png"));
console.log(svgPath);
