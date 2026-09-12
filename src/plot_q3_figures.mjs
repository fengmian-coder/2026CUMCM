import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
const root=process.cwd(),out=path.join(root,'figures');
const C={ink:'#263746',blue:'#466F87',cyan:'#78B6C8',yellow:'#F2D98E',coral:'#E48578',green:'#98AF1E'};
const all=JSON.parse(fs.readFileSync(path.join(root,'outputs/q3/all_subsets.json'),'utf8'));
const metrics=JSON.parse(fs.readFileSync(path.join(root,'outputs/q3/forecast_metrics_w28.json'),'utf8'));
const W=1600,H=900;
const wrap=body=>`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><rect width="100%" height="100%" fill="white"/><style>text{font-family:'Microsoft YaHei',sans-serif;fill:${C.ink};font-size:24px}.grid{stroke:#e3e3de;stroke-width:1.4}</style>${body}</svg>`;
async function save(name,body){const svg=wrap(body);fs.writeFileSync(path.join(out,name+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(out,name+'.png'));}
{
  const keys=['only_0','updates_06','updates_12','updates_18','updates_0612','updates_0618','updates_1218','updates_061218'],labels=['00:00','00:00、06:00','00:00、12:00','00:00、18:00','00:00、06:00、12:00（主方案）','00:00、06:00、18:00','00:00、12:00、18:00','00:00、06:00、12:00、18:00'];
  const v=keys.map(k=>all.find(x=>x.case===k).natural_totals.total_cost_yuan/10000);
  const x=a=>570+(a-1435)/20*850;let b='<text x="800" y="70" text-anchor="middle" style="font-size:36px;font-weight:bold">八种预报时点组合的实际总费用</text>';
  for(let a=1435;a<=1455;a+=5)b+=`<line x1="${x(a)}" y1="130" x2="${x(a)}" y2="730" class="grid"/><text x="${x(a)}" y="780" text-anchor="middle">${a}</text>`;
  v.forEach((a,i)=>{const y=165+i*78,c=i===4?C.green:i===7?C.coral:C.blue;b+=`<text x="540" y="${y+8}" text-anchor="end">${labels[i]}</text><circle cx="${x(a)}" cy="${y}" r="10" fill="${c}"/><text x="${x(a)+18}" y="${y-15}">${a.toFixed(4)}</text>`;});
  b+='<text x="920" y="850" text-anchor="middle">2025年2—12月自然日总费用 / 万元</text>';await save('q3_update_cost_comparison',b);
}
{
  const names=['Q','A','selected'],labels=['第二问预测','附件3预报','历史择优结果'],colors=[C.blue,C.coral,C.green];
  const xs=[260,630,1000,1370],ys=v=>730-v/220*530;
  let b='<text x="800" y="70" text-anchor="middle" style="font-size:36px;font-weight:bold">各发布时间光伏预测误差</text>';
  for(let v=0;v<=200;v+=50)b+=`<line x1="180" y1="${ys(v)}" x2="1450" y2="${ys(v)}" class="grid"/><text x="150" y="${ys(v)+8}" text-anchor="end">${v}</text>`;
  names.forEach((name,i)=>{const values=['0','6','12','18'].map(h=>metrics[h][name].mae_kw);b+=`<path d="${values.map((v,j)=>`${j?'L':'M'} ${xs[j]} ${ys(v)}`).join(' ')}" fill="none" stroke="${colors[i]}" stroke-width="4"/>`;values.forEach((v,j)=>b+=`<circle cx="${xs[j]}" cy="${ys(v)}" r="8" fill="${colors[i]}"/>`);b+=`<line x1="${320+i*360}" y1="125" x2="${365+i*360}" y2="125" stroke="${colors[i]}" stroke-width="5"/><text x="${380+i*360}" y="133">${labels[i]}</text>`;});
  ['00:00','06:00','12:00','18:00'].forEach((v,i)=>b+=`<text x="${xs[i]}" y="785" text-anchor="middle">${v}</text>`);
  b+='<text x="800" y="850" text-anchor="middle">预报发布时间</text><text x="60" y="470" text-anchor="middle" transform="rotate(-90 60 470)">MAE / kW</text>';await save('q3_forecast_mae',b);
}
console.log('Saved Q3 comparison figures');
