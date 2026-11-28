// 字形检查与字体样张：按片中实际字体逐字检查缺字（豆腐块/空白），并输出字体样张图。
// 文案登记：film.html 中定义 window.TEXT_SPECS = [{role:'主句', font:"900 120px 'Songti SC'", text:'踩出自己的路'}, ...]
const fs=require('fs'),path=require('path');
function registerProjectFonts(GlobalFonts,projectDir){const dir=path.join(projectDir,'fonts');const out=[];if(!fs.existsSync(dir))return out;
 for(const f of fs.readdirSync(dir)){if(/\.(ttf|otf|ttc|woff2?)$/i.test(f)){try{GlobalFonts.registerFromPath(path.join(dir,f));out.push(f)}catch(e){out.push(f+' (注册失败: '+e.message+')')}}}return out}
function checkSpecs(createCanvas,specs){
 const size=96,box=size*2;function draw(ch,font){const c=createCanvas(box,box),x=c.getContext('2d');x.font=font.replace(/\d+(\.\d+)?px/,size+'px');x.fillStyle='#000';x.textBaseline='middle';x.fillText(ch,size*0.3,box/2);
  const d=x.getImageData(0,0,box,box).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>0)n++;return {ink:n,png:c.toBuffer('image/png')}}
 const problems=[];
 for(const s of specs){const tofu=draw('\u0378',s.font).png;const seen=new Set();
  for(const ch of [...String(s.text)]){if(seen.has(ch)||/\s/.test(ch))continue;seen.add(ch);const r=draw(ch,s.font);
   if(r.ink===0)problems.push({role:s.role,font:s.font,char:ch,kind:'空白'});else if(r.png.equals(tofu))problems.push({role:s.role,font:s.font,char:ch,kind:'豆腐块'})}}
 return problems}
function specimen(createCanvas,specs,problems,file){
 const W=1920,rowH=Math.max(120,Math.min(220,Math.floor(1000/Math.max(1,specs.length))));const H=Math.max(1080,80+rowH*specs.length);const c=createCanvas(W,H),x=c.getContext('2d');
 x.fillStyle='#efebe3';x.fillRect(0,0,W,H);x.fillStyle='#151515';x.font="bold 30px 'Courier New'";x.fillText('TYPE SPECIMEN',60,52);
 specs.forEach((s,i)=>{const y=80+i*rowH;x.strokeStyle='rgba(0,0,0,0.15)';x.beginPath();x.moveTo(60,y);x.lineTo(W-60,y);x.stroke();
  x.fillStyle='#555';x.font="bold 22px 'Courier New'";x.fillText(String(s.role||''),60,y+34);x.font="18px 'Courier New'";x.fillText(s.font.slice(0,46),60,y+62);
  const m=s.font.match(/(\d+(?:\.\d+)?)px/);let px=m?Number(m[1]):80;px=Math.min(px,rowH*0.62);x.font=s.font.replace(/\d+(\.\d+)?px/,px+'px');
  let w=x.measureText(s.text).width;const maxW=W-660;if(w>maxW){px*=maxW/w;x.font=s.font.replace(/\d+(\.\d+)?px/,px+'px')}
  x.fillStyle=s.color||'#151515';x.textBaseline='middle';const bx=600,by=y+rowH/2;x.fillText(s.text,bx,by);x.textBaseline='alphabetic';
  const bad=new Set(problems.filter(p=>p.role===s.role&&p.font===s.font).map(p=>p.char));if(bad.size){let cx=bx;for(const ch of [...String(s.text)]){const cw=x.measureText(ch).width;if(bad.has(ch)){x.strokeStyle='#e00';x.lineWidth=4;x.strokeRect(cx-2,by-px*0.6,cw+4,px*1.2)}cx+=cw}
   x.fillStyle='#e00';x.font="bold 22px 'Courier New'";x.fillText('MISSING: '+[...bad].join(' '),60,y+rowH-14)}});
 fs.writeFileSync(file,c.toBuffer('image/png'))}
module.exports={registerProjectFonts,checkSpecs,specimen};
