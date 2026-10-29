import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createBlobDatabase} from './netlify/functions/api.mjs';
import {handle} from './netlify/functions/api.mjs';
const seed=JSON.parse(readFileSync(new URL('./seed.json',import.meta.url)));
class Store {
  constructor(){this.entries=new Map();this.sequence=0;this.fail=false;}
  async getWithMetadata(key,options){assert.equal(options.consistency,'strong');return structuredClone(this.entries.get(key)??null);}
  async setJSON(key,data,options){
    if(this.fail)throw new Error('Storage outage');
    const current=this.entries.get(key);
    if((options.onlyIfNew&&current)||(options.onlyIfMatch&&current?.etag!==options.onlyIfMatch))return {modified:false};
    const etag='"'+(++this.sequence)+'"';this.entries.set(key,{data:structuredClone(data),etag,metadata:{}});return {modified:true,etag};
  }
}
function fixture(){
  const store=new Store();
  async function call(path,body,token='demo-owner'){
    const r=await handle(new Request('https://demo.invalid'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token},...(body===undefined?{}:{body:JSON.stringify(body)})}),{DB:createBlobDatabase(store)},seed);
    return {status:r.status,data:await r.json()};
  }
  return {store,call};
}
test('Netlify backend loads all seven profiles and owner/advisor books',async()=>{
  const {call}=fixture();assert.equal((await call('/api/profiles')).data.profiles.length,7);
  for(const p of seed.profiles){const r=await call('/api/book',undefined,p.token);assert.equal(r.status,200);assert.ok(r.data.clients.length);}
});
test('Blobs persists portfolios across fresh function instances without reseeding',async()=>{
  const {call,store}=fixture(),hid='demo-mehta';
  let r=await call('/api/create-portfolio',{client:hid,type:'personal',name:'Persistent education',opening_cash:500});assert.equal(r.status,200);
  const pf=Object.values(r.data.accounts).find(r=>r.name==='Persistent education');
  r=await call('/api/invest',{client:hid,account:pf.id,name:'Demo bond',kind:'Bonds',amount:200});assert.equal(r.status,200);
  const reloaded=(await call('/api/portfolio?id='+hid)).data;assert.equal(reloaded.accounts[pf.id].cash,300);assert.equal(reloaded.accounts[pf.id].assets[0].value,200);
  assert.equal(store.entries.get('workspace/demo-v1').data.version,2);
});
test('Netlify atomic ETag writes reject one simultaneous debit',async()=>{
  const {call}=fixture();await call('/api/book');
  const results=await Promise.all([1,2].map(i=>call('/api/invest',{client:'demo-mehta',account:'education',kind:'Funds',name:'Concurrent '+i,amount:30000})));
  assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);
  assert.equal((await call('/api/portfolio?id=demo-mehta')).data.accounts.education.cash,15000);
});
test('Netlify simultaneous first requests seed exactly once',async()=>{
  const {call,store}=fixture();const results=await Promise.all([call('/api/book'),call('/api/book')]);assert.ok(results.every(r=>r.status===200));assert.equal(store.entries.size,1);assert.equal(store.entries.get('workspace/demo-v1').data.version,0);
});
test('Netlify storage failure does not report a successful mutation',async()=>{
  const {call,store}=fixture();await call('/api/book');const before=structuredClone(store.entries);store.fail=true;
  const r=await call('/api/invest',{client:'demo-mehta',account:'education',kind:'Funds',name:'Unsaved',amount:100});assert.equal(r.status,503);assert.deepEqual(store.entries,before);
});
test('backend access and account-aware chat still apply through Netlify storage',async()=>{
  const {call}=fixture();assert.equal((await call('/api/chat',{client:'demo-mehta',account:'retirement',question:'Cash?'},'demo-ma')).status,403);
  const r=await call('/api/chat',{client:'demo-mehta',account:'retirement',question:'Cash?'});assert.equal(r.status,200);assert.match(r.data.answer,/180,000/);
  assert.equal((await call('/api/chat?id=demo-mehta&account=retirement')).data.messages.length,2);
});
