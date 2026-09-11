// Interval-constant signed areas. Values remain unrounded; only drawing geometry changes.
export function signedArea(p, values, dt, positive, negative) {
  return [[1,positive],[-1,negative]].map(([sign,color])=>{
    let d=`M ${p.x(0)} ${p.y(0)}`;
    values.forEach((value,i)=>{
      const v=sign>0?Math.max(value,0):Math.min(value,0);
      d+=` V ${p.y(v)} H ${p.x((i+1)*dt)}`;
    });
    d+=` V ${p.y(0)} Z`;
    return `<path d="${d}" fill="${color}" fill-opacity="0.62" stroke="${color}" stroke-width="1.5"/>`;
  }).join('');
}
