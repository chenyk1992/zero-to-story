// 用法：node check-glyphs.cjs <project>/film.html [样张输出.png]
// 只读取 window.TEXT_SPECS，不需要素材图。发现缺字时退出码为 1。
const fs=require('fs'),path=require('path'),vm=require('vm');
const src=path.resolve(process.argv[2]||'');if(!process.argv[2])throw Error('Usage: node check-glyphs.cjs <project>/film.html [specimen.png]');
const canvasPath=process.env.CANVAS_MODULE||require.resolve('@napi-rs/canvas',{paths:[path.dirname(src),process.cwd(),__dirname]});
const {createCanvas,GlobalFonts}=require(canvasPath);const G=require('./glyph-check.cjs');
const fonts=G.registerProjectFonts(GlobalFonts,path.dirname(src));
const html=fs.readFileSync(src,'utf8');const code=(html.match(/window\.TEXT_SPECS\s*=\s*(\[[\s\S]*?\]);/)||[])[1];
if(!code)throw Error('film.html 中没有 window.TEXT_SPECS 文案登记');
const specs=vm.runInNewContext('('+code+')',{});const problems=G.checkSpecs(createCanvas,specs);
const out=path.resolve(process.argv[3]||path.join(path.dirname(src),'type-specimen.png'));G.specimen(createCanvas,specs,problems,out);
console.log(JSON.stringify({projectFonts:fonts,specs:specs.length,problems,specimen:out},null,2));process.exitCode=problems.length?1:0;
