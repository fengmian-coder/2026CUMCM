import { signedArea } from './q1_plot_elements.mjs';
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
const root=path.resolve(import.meta.dirname,'..');
const read=f=>fs.readFileSync(path.join(root,f),'utf8').replace(/^\uFEFF/,'').trim().split(/\r?\n/).slice(1).map(r=>r.split(','));
const a=read('outputs/q1_milp_schedule.csv'),b=read('outputs/q1_dp/dp_schedule_finest_grid.csv');
if(a.length!==144||b.length!==144)throw Error('Expected 144 intervals');
for(let i=0;i<144;i++)for(const j of [1,2,3,4])if(a[i][j]!==b[i][j])throw Error(`Source alignment mismatch ${i},${j}`);
const C={blue:'#466F87',coral:'#E48578',green:'#98AF1E',ink:'#263746'};
const col=(r,j,k=1)=>r.map(v=>Number(v[j])*k),energy=r=>[+r[0][9],...col(r,10)];
const cost=r=>r.reduce((s,v)=>s+Number(v[2])*Number(v[5]),0);
const ca=cost(a),cb=cost(b);
const txt=(x,y,s,size=24,anchor='middle')=>`<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${s}</text>`;
const line=(x1,y1,x2,y2,c='#DDE2E4',w=1,dash='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="${w}" stroke-dasharray="${dash}"/>`;
function panel(x0,y0,w,h,lo,hi,ticks,label){
 const x=v=>x0+v/24*w,y=v=>y0+h-(v-lo)/(hi-lo)*h;
 let s=ticks.map(v=>line(x0,y(v),x0+w,y(v))+txt(x0-18,y(v)+8,v,24,'end')).join('');
 s+=[0,4,8,12,16,20,24].map(v=>line(x(v),y0+h,x(v),y0+h+8,C.ink)+txt(x(v),y0+h+39,v)).join('');
 s+=line(x0,y0,x0,y0+h,C.ink,1.5)+line(x0,y0+h,x0+w,y0+h,C.ink,1.5)+txt(x0+w/2,y0+h+88,'时间 / h',28);
 s+=`<g transform="translate(${x0-110} ${y0+h/2}) rotate(-90)">${txt(0,0,label,28)}</g>`;
 return {x,y,s,w};
}
function curve(p,v,c,step=false){let d=`M ${p.x(0)} ${p.y(v[0])}`;if(step){for(let i=0;i<v.length;i++){if(i)d+=` V ${p.y(v[i])}`;d+=` H ${p.x((i+1)/6)}`;}}else for(let i=1;i<v.length;i++)d+=` L ${p.x(i/6)} ${p.y(v[i])}`;return `<path d="${d}" fill="none" stroke="${c}" stroke-width="3.5" stroke-linejoin="round"/>`;}
function bars(p,r){return signedArea(p,r.map(v=>(+v[7]- +v[6])*6),1/6,C.green,C.coral);}
async function save(name,title,body,H=980){let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="${H}" viewBox="0 0 1800 ${H}"><rect width="100%" height="100%" fill="white"/><style>text{font-family:'Microsoft YaHei','Noto Sans CJK SC',sans-serif;fill:${C.ink}}</style><g font-weight="600">${txt(900,62,title,36)}</g>${body}</svg>`;fs.writeFileSync(path.join(root,`figures/${name}.svg`),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(root,`figures/${name}.png`));}
let s=txt(500,115,`MILP   |   ${ca.toFixed(2)} 元`,28)+txt(1380,115,`DP（5 kWh）   |   ${cb.toFixed(2)} 元`,28);
const max=Math.ceil(Math.max(...col(a,5,6),...col(b,5,6))/2000)*2000;
for(const [k,r] of [a,b].entries()){
 const x=165+k*880;
 let p=panel(x,200,650,220,0,max,[0,max/2,max],'购电功率 / kW');s+=p.s+curve(p,col(r,5,6),C.blue,true);
 p=panel(x,570,650,220,-5500,5500,[-5000,0,5000],'储能功率 / kW');s+=p.s+bars(p,r);
 p=panel(x,940,650,220,0,100,[0,50,100],'SOC / %');s+=p.s+line(x,p.y(10),x+650,p.y(10),C.coral,1.5,'8 6')+line(x,p.y(90),x+650,p.y(90),C.green,1.5,'8 6')+curve(p,energy(r).map(v=>v/12000*100),C.blue);
}
s+=line(630,153,675,153,C.green,4)+txt(690,161,'放电（正）',23,'start')+line(970,153,1015,153,C.coral,4)+txt(1030,161,'充电（负）',23,'start');
await save('q1_milp_dp_comparison','MILP 与动态规划的日内调度对比',s,1300);
const ea=energy(a),delta=energy(b).map((v,i)=>v-ea[i]),lim=Math.max(10,Math.ceil(Math.max(...delta.map(Math.abs))/10)*10);
const p=panel(165,170,1470,650,-lim,lim,[-lim,-lim/2,0,lim/2,lim],'储电量差 / kWh');
await save('q1_milp_dp_difference','储电量轨迹差（DP − MILP）',p.s+line(165,p.y(0),1635,p.y(0),C.ink,1.5,'8 6')+curve(p,delta,C.coral));
console.log(JSON.stringify({milp_cost:ca,dp_cost:cb,cost_gap:cb-ca,max_absolute_energy_difference:Math.max(...delta.map(Math.abs))}));
