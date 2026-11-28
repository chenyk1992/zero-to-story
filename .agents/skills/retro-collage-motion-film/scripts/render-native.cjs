// Local prototype fallback: executes this self-contained scene using a Canvas 2D backend.
const fs=require('fs'),path=require('path'),vm=require('vm'),{spawnSync}=require('child_process');
const GC=require('./glyph-check.cjs');
const resolveCanvas=(srcDir)=>require(process.env.CANVAS_MODULE||require.resolve('@napi-rs/canvas',{paths:[srcDir,process.cwd(),__dirname]}));
async function main(){
if(!process.argv[2])throw Error('Usage: node render-native.cjs <project>/film.html <output-dir>');const source=path.resolve(process.argv[2]);
const {createCanvas,loadImage,GlobalFonts}=resolveCanvas(path.dirname(source));
const dir=path.resolve(process.argv[3]||'output');fs.mkdirSync(dir,{recursive:true});
const projectFonts=GC.registerProjectFonts(GlobalFonts,path.dirname(source));const html=fs.readFileSync(source,'utf8');
const dims=html.match(/<canvas[^>]*width="(\d+)"[^>]*height="(\d+)"/);if(!dims)throw Error('Canvas dimensions missing');const canvas=createCanvas(Number(dims[1]),Number(dims[2])),controls={};
const document={querySelector:()=>canvas,getElementById:id=>controls[id]||(controls[id]={value:0}),createElement:()=>createCanvas(280,300)};
const sandbox={document,window:{RENDER_MODE:true},performance:{now:()=>0},requestAnimationFrame:()=>{},scrub:document.getElementById('scrub'),toggle:document.getElementById('toggle'),console};sandbox.window=sandbox;sandbox.RENDER_MODE=true;sandbox.SCENE_OVERRIDES=JSON.parse(process.env.SCENE_OVERRIDES||'{}');const manifest=path.join(path.dirname(source),path.basename(source,'.html')+'-assets.json');if(fs.existsSync(manifest)){sandbox.PRELOADED_ASSETS={};for(const [id,file] of Object.entries(JSON.parse(fs.readFileSync(manifest,'utf8')))){sandbox.PRELOADED_ASSETS[id]=await loadImage(path.resolve(path.dirname(source),file));}}vm.createContext(sandbox);vm.runInContext(html.match(/<script>([\s\S]*)<\/script>/)[1],sandbox);if(sandbox.ready)await sandbox.ready;
const specs=sandbox.window.TEXT_SPECS;if(!specs)throw Error('film.html 缺少 window.TEXT_SPECS 文案登记，无法做缺字检查');const glyphProblems=GC.checkSpecs(createCanvas,specs);if(glyphProblems.length){console.error(JSON.stringify(glyphProblems,null,2));throw Error('发现缺字（豆腐块/空白），已停止渲染：先换用包含这些字的字体')}
const frames=path.resolve(process.env.FRAMES_DIR||path.join(dir,'frames'));fs.mkdirSync(frames,{recursive:true});
const cfg=sandbox.window.CONFIG,count=Math.round(cfg.duration*cfg.fps);
for(let i=0;i<count;i++){sandbox.window.seek(i/cfg.fps);fs.writeFileSync(path.join(frames,String(i).padStart(5,'0')+'.png'),canvas.toBuffer('image/png'))}
const seekChecks=[.1,.9,2.2,3.3,4.8,5.7,6.9,7.8,9.8,10.7,11.9,13.3,14.7].filter(t=>t<cfg.duration);for(const t of seekChecks){sandbox.seek(t);const a=canvas.toBuffer('image/png');sandbox.seek(cfg.duration*.91);sandbox.seek(.02);sandbox.seek(t);if(!a.equals(canvas.toBuffer('image/png')))throw Error('nondeterministic seek at '+t)}const stable=true;
const output=path.join(dir,path.basename(source,'.html')+'-preview.mp4');const p=spawnSync(process.env.FFMPEG||'ffmpeg',['-y','-hide_banner','-loglevel','error','-framerate',String(cfg.fps),'-i',path.join(frames,'%05d.png'),'-frames:v',String(count),'-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',output],{stdio:'inherit'});if(p.status!==0)throw Error('encode failed');
fs.writeFileSync(path.join(dir,'render-report.json'),JSON.stringify({config:cfg,frames:count,deterministicSeek:stable,seekCheckTimes:seekChecks,assets:Object.keys(sandbox.PRELOADED_ASSETS||{}),sceneTimeline:sandbox.SCENES||null,renderer:'@napi-rs/canvas local fallback',projectFonts,glyphCheck:{specs:specs.length,problems:0},audio:'none; visual prototype',provenance:'Renderer does not establish model authorship; see project provenance record',pending:['cross-renderer pixel parity','final audio mux']},null,2));console.log(output);

}main().catch(e=>{console.error(e);process.exitCode=1});
