const fs=require('fs'),path=require('path'),{spawnSync}=require('child_process');
const report={node:process.version,platform:process.platform,arch:process.arch,canvas:null,ffmpeg:null,ffprobe:null};
const searchPaths=[process.argv[2]?path.resolve(process.argv[2]):null,process.cwd(),__dirname].filter(Boolean);
try{const resolved=process.env.CANVAS_MODULE||require.resolve('@napi-rs/canvas',{paths:searchPaths});const mod=require(resolved);const c=mod.createCanvas(16,16);c.getContext('2d').fillRect(0,0,16,16);report.canvas={ok:c.toBuffer('image/png').length>0,module:resolved}}catch(e){report.canvas={ok:false,error:e.message}}
for(const name of ['ffmpeg','ffprobe']){const candidates=[process.env[name.toUpperCase()],name,...(process.platform==='darwin'?[`/Applications/MiniMax Design.app/Contents/Resources/ffmpeg/${name}`]:[])].filter(Boolean);report[name]={ok:false};for(const bin of candidates){const p=spawnSync(bin,['-version'],{encoding:'utf8'});if(p.status===0){report[name]={ok:true,bin,version:p.stdout.split('\n')[0].trim()};break}}}
report.ready=report.canvas.ok&&report.ffmpeg.ok&&report.ffprobe.ok;console.log(JSON.stringify(report,null,2));process.exitCode=report.ready?0:1;
