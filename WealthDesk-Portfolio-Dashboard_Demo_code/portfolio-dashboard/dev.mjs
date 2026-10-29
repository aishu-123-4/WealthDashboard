import {spawn} from 'node:child_process';
const child=spawn(process.platform==='win32'?'python':'python3',['app.py',...process.argv.slice(2)],{stdio:'inherit'});
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code??1));
