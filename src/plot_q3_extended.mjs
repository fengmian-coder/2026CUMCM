import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
const root=process.cwd(), out=path.join(root,'figures');
const d=JSON.parse(fs.readFileSync(path.join(root,'outputs/q3/plot_data.json'),'utf8'));
const C={ink:'#263746',blue:'#466F87',cyan:'#78B6C8',yellow:'#F2D98E',coral:'#E48578',green:'#98AF1E'};
const text=(x,y,s,size=24,anchor='middle')=>`<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${s}</text>`;
const line=(x,y,X,Y,c='#dededb',w=1.2)=>`<line x1="${x}" y1="${y}" x2="${X}" y2="${Y}" stroke="${c}" stroke-width="${w}"/>`;
async function save(name,title,body){let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="950"><rect width="1600" height="950" fill="white"/><g font-family="Microsoft YaHei, sans-serif" fill="${C.ink}">${text(800,65,title,36)}${body}</g></svg>`;fs.writeFileSync(path.join(out,name+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(out,name+'.png'));}
function mix(a,b,t){let x=a.match(/\w\w/g).map(v=>parseInt(v,16)),y=b.match(/\w\w/g).map(v=>parseInt(v,16));return '#'+x.map((v,i)=>Math.round(v+(y[i]-v)*t).toString(16).padStart(2,'0')).join('');}
function heat(matrix,lo,hi,div=false){let s='',x=160,y=145,w=1250,h=660;
 matrix.forEach((r,i)=>r.forEach((v,j)=>{let t=Math.max(0,Math.min(1,(v-lo)/(hi-lo)));let c=div?(t<.5?mix('466F87','FFFFFF',t*2):mix('FFFFFF','E48578',(t-.5)*2)):mix('F2D98E','466F87',t);if(!div&&lo===0&&v===0)c='#f7f7f5';s+=`<rect x="${x+j*w/144}" y="${y+i*h/matrix.length}" width="${w/144+.1}" height="${h/matrix.length+.1}" fill="${c}"/>`;}));
 for(let k=0;k<=24;k+=4)s+=text(x+w*k/24,850,k);
 for(let m=2;m<=12;m+=2){let i=d.dates.indexOf(`2025-${String(m).padStart(2,'0')}-01`);s+=text(140,y+i*h/matrix.length+8,`${m}月`,24,'end');}
 for(let i=0;i<150;i++){let t=i/149,c=div?(t<.5?mix('E48578','FFFFFF',t*2):mix('FFFFFF','466F87',(t-.5)*2)):mix('466F87','F2D98E',t);s+=`<rect x="1460" y="${180+i*3.7}" width="24" height="4" fill="${c}"/>`;}
 s+=text(1472,158,hi.toFixed(1),20)+text(1472,768,lo.toFixed(1),20)+text(780,915,'时间 / h');return s;}
await save('q3_soc_heatmap','第三问储能荷电状态 / %',heat(d.soc,10,90));
const emMax=Math.max(...d.emergency.flat());
await save('q3_emergency_heatmap','第三问紧急购电分布 / kWh',heat(d.emergency,0,emMax));
const adMax=Math.max(...d.adjustment.flat().map(Math.abs));
await save('q3_adjustment_heatmap','最终购电量相对零点计划的变化 / kWh',heat(d.adjustment,-adMax,adMax,true));
function panel(x,y,w,h,arrays,colors,lo,hi,xmax,xlabel,ylabel,step=false){let s='';const xx=v=>x+v/xmax*w,yy=v=>y+h-(v-lo)/(hi-lo)*h;
 for(let i=0;i<=4;i++){let v=lo+(hi-lo)*i/4;s+=line(x,yy(v),x+w,yy(v))+text(x-15,yy(v)+7,v.toFixed(0),21,'end');}
 for(let i=0;i<=6;i++)s+=text(xx(xmax*i/6),y+h+36,(xmax*i/6).toFixed(0),21);
 arrays.forEach((a,k)=>{let pts=a.map((v,i)=>{let X=xx(i*xmax/(step?a.length:a.length-1)),Y=yy(v);return i?(step?`H ${X} V ${Y}`:`L ${X} ${Y}`):`M ${X} ${Y}`;}).join(' ');if(step)pts+=` H ${xx(xmax)}`;s+=`<path d="${pts}" fill="none" stroke="${colors[k]}" stroke-width="2.8"/>`;});
 s+=text(x+w/2,y+h+85,xlabel)+`<text x="${x-83}" y="${y+h/2}" text-anchor="middle" transform="rotate(-90 ${x-83} ${y+h/2})" font-size="24">${ylabel}</text>`;return s;}
let t=d.typical,top=Math.ceil(Math.max(...t.baseline,...t.purchase)/100)*100;
let body=text(800,115,`代表日 ${d.dates[d.typical_index]} · 按全天购电调整绝对量排序选中位日`,22);
body+=text(475,172,'零点计划',23)+line(350,164,410,164,C.blue,4)+text(1080,172,'最终购电',23)+line(950,164,1010,164,C.coral,4);
body+=panel(150,220,600,480,[t.baseline,t.purchase],[C.blue,C.coral],0,top,24,'时间 / h','购电量 / kWh',true);
body+=panel(940,220,520,480,[t.energy.map(v=>v/12000*100)],[C.green],0,100,24,'时间 / h','SOC / %');
await save('q3_representative_day','代表日购电计划调整与储能状态',body);
let cum=d.cumulative_difference,lo=Math.floor(Math.min(0,...cum)/1000)*1000,hi=Math.ceil(Math.max(...cum)/1000)*1000;
body=panel(160,180,1270,590,[cum],[C.coral],lo,hi,333,'自 2025年2月1日起的日序号','累计费用差 / 元');
body+=text(800,115,'四时点方案 − 仅 00:00、06:00、12:00 方案',24);
await save('q3_18h_cumulative_difference','加入18:00更新后的累计费用差',body);
let vals=d.monthly.flatMap(r=>[r.grid_difference,r.emergency_difference]);lo=Math.floor(Math.min(0,...vals)/500)*500;hi=Math.ceil(Math.max(0,...vals)/500)*500;
body=text(800,112,'四时点方案 − 仅 00:00、06:00、12:00 方案',23);
const yy=v=>750-(v-lo)/(hi-lo)*520;
for(let i=0;i<=4;i++){let v=lo+(hi-lo)*i/4;body+=line(170,yy(v),1440,yy(v))+text(150,yy(v)+8,v.toFixed(0),22,'end');}
body+=line(170,yy(0),1440,yy(0),C.ink,1.8);
d.monthly.forEach((r,i)=>{let x=220+i*115;body+=line(x-14,yy(r.grid_difference),x+14,yy(r.emergency_difference),'#aeb6ba',2);for(const [off,v,c]of [[-14,r.grid_difference,C.coral],[14,r.emergency_difference,C.blue]])body+=`<circle cx="${x+off}" cy="${yy(v)}" r="8" fill="${c}"/>`;body+=text(x,800,`${r.month}月`,22);});
body+=text(600,170,'● 外网结算费差',24)+text(1070,170,'● 紧急购电费差',24)+line(340,161,400,161,C.coral,5)+line(800,161,860,161,C.blue,5)+text(800,885,'月份')+`<text x="60" y="480" text-anchor="middle" transform="rotate(-90 60 480)" font-size="24">费用差 / 元</text>`;
await save('q3_monthly_cost_difference','18:00更新的月度费用分解',body);
console.log('Saved six Q3 supplementary figures');
