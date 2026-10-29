import {mkdir,copyFile,readFile} from 'node:fs/promises';
const source=new URL('./WealthDesk-Portfolio-Dashboard_Demo_code/portfolio-dashboard/web/',import.meta.url);
const output=new URL('./dist/',import.meta.url);
await mkdir(output,{recursive:true});
for(const name of ['index.html','app.js','style.css']) await copyFile(new URL(name,source),new URL(name,output));
const page=await readFile(new URL('index.html',output),'utf8');
if(!page.includes('WealthDesk')||!page.includes('/app.js')) throw new Error('Dashboard entrypoint is incomplete');
console.log('Published dashboard assets to dist/; Netlify deploys the API function separately.');
