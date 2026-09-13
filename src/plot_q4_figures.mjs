import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';
const root=process.cwd(),out=path.join(root,'figures');
const d=JSON.parse(fs.readFileSync(path.join(root,'outputs/q4/figure_data.json'),'utf8'));
const C={ink:'#263746',blue:'#466F87',cyan:'#78B6C8',yellow:'#F2D98E',coral:'#E48578',green:'#98AF1E'};
const text=(x,y,s,size=24,anchor='middle')=>`<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}">${s}</text>`;
const line=(x,y,X,Y,c='#e0e3e4',w=1.2,dash='')=>`<line x1="${x}" y1="${y}" x2="${X}" y2="${Y}" stroke="${c}" stroke-width="${w}" ${dash?`stroke-dasharray="${dash}"`:''}/>`;
const dot=(x,y,c,r=7)=>`<circle cx="${x}" cy="${y}" r="${r}" fill="${c}"/>`;
function legend(items,y=115){return items.map((r,i)=>{const x=900-(items.length-1)*185+i*370;return line(x-115,y-8,x-65,y-8,r.color,4,r.dash)+text(x-48,y,r.label,23,'start');}).join('');}
async function save(name,title,body,height=1100){const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="${height}" viewBox="0 0 1800 ${height}"><rect width="100%" height="100%" fill="white"/><g fill="${C.ink}" font-family="Microsoft YaHei, sans-serif">${text(900,60,title,36)}${body}</g></svg>`;fs.writeFileSync(path.join(out,name+'.svg'),svg);await sharp(Buffer.from(svg)).png().toFile(path.join(out,name+'.png'));}
function panel({x,y,w=650,h=300,lo=0,hi=1,xlo=0,xhi=24,ticks=[0,6,12,18,24],labels=null,xlabel='计划时刻 / h:min',ylabel='',title='',fmt=v=>String(Number(v.toFixed(2)))}){
 const xx=v=>x+(v-xlo)/(xhi-xlo)*w, yy=v=>y+h-(v-lo)/(hi-lo)*h;
 let s=text(x+w/2,y-25,title,26);
 for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;s+=line(x,yy(v),x+w,yy(v))+text(x-18,yy(v)+8,fmt(v),21,'end');}
 ticks.forEach((v,i)=>s+=text(xx(v),y+h+35,labels?labels[i]:v,21));
 s+=line(x,y,x,y+h,C.ink)+line(x,y+h,x+w,y+h,C.ink)+text(x+w/2,y+h+77,xlabel,23)+`<text x="${x-100}" y="${y+h/2}" font-size="23" text-anchor="middle" transform="rotate(-90 ${x-100} ${y+h/2})">${ylabel}</text>`;
 function curve(values,color,{xs=null,step=false,dash='',dots=false}={}){let p='';values.forEach((v,i)=>{const X=xx(xs?xs[i]:xlo+i*(xhi-xlo)/(step?values.length:values.length-1)),Y=yy(v);p+=i?(step?` H ${X} V ${Y}`:` L ${X} ${Y}`):`M ${X} ${Y}`;});if(step)p+=` H ${xx(xhi)}`;return `<path d="${p}" fill="none" stroke="${color}" stroke-width="3" ${dash?`stroke-dasharray="${dash}"`:''}/>`+(dots?values.map((v,i)=>dot(xx(xs?xs[i]:xlo+i*(xhi-xlo)/(values.length-1)),yy(v),color)).join(''):'');}
 return {s,xx,yy,curve};
}
const clock=['00:10','06:10','12:10','18:10','次日00:10'];
{
 let b=legend([{label:'实际电价',color:C.blue},{label:'M0预测',color:C.coral,dash:'10 5'}]);
 const hi=Math.ceil(Math.max(...d.forecast.flatMap(r=>[...r.actual,...r.prediction]))*5)/5;
 d.forecast.forEach((r,i)=>{const a=panel({x:i%2?1040:180,y:i<2?205:680,h:275,hi,labels:clock,ylabel:'电价 / (元/kWh)',title:r.date});b+=a.s+a.curve(r.actual,C.blue,{step:true})+a.curve(r.prediction,C.coral,{step:true,dash:'10 5'});});
 await save('q4_price_forecast','指定日期实际电价与M0预测',b);
}
{
 let b=legend([{label:'固定电价',color:C.blue},{label:'波动电价',color:C.coral}]);
 const hi=Math.ceil(Math.max(...d.annual.map(r=>r.total_cost/10000))/100)*100;
 for(const m of [2,3]){const a=panel({x:m===2?200:1060,y:220,w:600,h:620,lo:0,hi,xlo:-.25,xhi:2.25,ticks:[0,1,2],labels:['完整费用','外网结算费','紧急购电费'],xlabel:'费用组成',ylabel:'费用 / 万元',title:`问题${m}`});b+=a.s;['total_cost','grid_fee','emergency_fee'].forEach((k,i)=>{const rows=d.annual.filter(r=>r.mode===m);b+=line(a.xx(i)-12,a.yy(rows[0][k]/10000),a.xx(i)+12,a.yy(rows[1][k]/10000),'#a9b1b5',2);rows.forEach((r,j)=>{const X=a.xx(i)+(j?12:-12),Y=a.yy(r[k]/10000);b+=dot(X,Y,j?C.coral:C.blue,9)+text(X+(j?16:-16),Y+(k==='emergency_fee'?-15:j?-14:27),(r[k]/10000).toFixed(2),20,j?'start':'end');});});}
 await save('q4_tariff_cost_comparison','固定电价与波动电价的费用构成',b);
}
{
 let b=legend([{label:'实际电价',color:C.blue},{label:'预测电价',color:C.coral,dash:'10 5'}]);
 b+=text(900,150,'2025-06-21，计划窗口为当天00:10至次日00:10',23);
 const r=d.forecast.find(r=>r.date==='2025-06-21');
 for(const t of d.dispatch){const x=t.mode===2?180:1040;
 const a=panel({x,y:235,h:220,hi:1.6,labels:clock,ylabel:'电价 / (元/kWh)',title:`问题${t.mode}`});b+=a.s+a.curve(r.actual,C.blue,{step:true})+a.curve(r.prediction,C.coral,{step:true,dash:'10 5'});
 const p=panel({x,y:635,h:220,lo:-6000,hi:12000,labels:clock,ylabel:'功率 / kW'});b+=p.s+line(x,p.yy(0),x+650,p.yy(0),'#7f898e',1.5)+p.curve(t.purchase_kw,C.blue,{step:true})+p.curve(t.storage_kw,C.green,{step:true});
 const e=panel({x,y:1035,h:220,lo:0,hi:100,labels:clock,ylabel:'SOC / %'});b+=e.s+e.curve(t.soc,C.green);}
 b+=legend([{label:'外网购电功率',color:C.blue},{label:'储能净输出功率',color:C.green}],590);
 await save('q4_price_dispatch','电价、购电与储能运行的对应关系',b,1380);
}
{
 let b=legend([{label:'固定电价',color:C.blue,dash:'10 5'},{label:'波动电价',color:C.coral}]);
 const hi=Math.ceil(Math.max(...d.monthly.flatMap(r=>[r.cost,r.fixed_cost]))/1e5)*10;
 const eh=Math.ceil(Math.max(...d.monthly.flatMap(r=>[r.emergency,r.fixed_emergency]))/10000);
 for(const m of [2,3]){const r=d.monthly.filter(r=>r.mode===m),xs=r.map(r=>r.month),x=m===2?180:1040;
 const a=panel({x,y:205,h:275,hi,xlo:2,xhi:12,ticks:[2,4,6,8,10,12],xlabel:'月份',ylabel:'总费用 / 万元',title:`问题${m}`});b+=a.s+a.curve(r.map(r=>r.fixed_cost/10000),C.blue,{xs,dash:'10 5',dots:true})+a.curve(r.map(r=>r.cost/10000),C.coral,{xs,dots:true});
 const e=panel({x,y:680,h:275,hi:eh,xlo:2,xhi:12,ticks:[2,4,6,8,10,12],xlabel:'月份',ylabel:'紧急购电量 / 万kWh'});b+=e.s+e.curve(r.map(r=>r.fixed_emergency/10000),C.blue,{xs,dash:'10 5',dots:true})+e.curve(r.map(r=>r.emergency/10000),C.coral,{xs,dots:true});}
 await save('q4_monthly_comparison','两种电价情形下的月度运行结果',b);
}
{
 let b=legend([{label:'问题2',color:C.blue},{label:'问题3',color:C.coral}]);
 const vals=d.sensitivity.map(r=>r.total_cost/10000),lo=Math.floor(Math.min(...vals)/10)*10,hi=Math.ceil(Math.max(...vals)/10)*10;
 const a=panel({x:180,y:250,h:580,lo,hi,xlo:30,xhi:100,ticks:[30,50,100],xlabel:'场景数量',ylabel:'总费用 / 万元',title:'固定种子20260912'});
 const b2=panel({x:1040,y:250,h:580,lo,hi,xlo:0,xhi:2,ticks:[0,1,2],labels:['20260912','20260913','20260914'],xlabel:'随机种子',ylabel:'总费用 / 万元',title:'固定30场景'});b+=a.s+b2.s;
 for(const m of [2,3]){const color=m===2?C.blue:C.coral;const get=l=>d.sensitivity.find(r=>r.mode===m&&r.label===l).total_cost/10000;b+=a.curve(['30','50','100'].map(get),color,{xs:[30,50,100],dots:true});['种子12','种子13','种子14'].forEach((l,i)=>b+=dot(b2.xx(i),b2.yy(get(l)),color,10));}
 await save('q4_sampling_sensitivity','场景数量与随机抽样的费用敏感性',b);
}
console.log('Saved five Q4 figures as PNG and SVG');
