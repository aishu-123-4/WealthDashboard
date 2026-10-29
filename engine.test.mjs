import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Ledger,handle} from './netlify/functions/api.mjs';
const seed=JSON.parse(readFileSync(new URL('./seed.json',import.meta.url)));
const hid='demo-mehta';
function database(){
  return {row:null,withSession(){return this;},prepare(sql){const db=this;return {bind(...args){return {
    async first(){return db.row?structuredClone(db.row):null;},
    async run(){
      if(sql.startsWith('INSERT')){if(!db.row)db.row={version:0,payload:args[1]};return {meta:{changes:1}};}
      if(db.row.version!==args[2])return {meta:{changes:0}};
      db.row={payload:args[0],version:db.row.version+1};return {meta:{changes:1}};
    }
  };}};}};
}
function app(options={}){
  const env={DB:database(),...options};
  async function call(path,body,token='demo-owner'){
    const response=await handle(new Request('https://test.invalid'+path,{method:body===undefined?'GET':'POST',headers:{Authorization:'Bearer '+token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})}),env,seed);
    return {status:response.status,data:await response.json()};
  }
  return {env,call,view:async()=> (await call('/api/portfolio?id='+hid)).data};
}
test('all seeded role books preserve original Python output',async()=>{
  const baseline=JSON.parse(readFileSync(new URL('./baseline.json',import.meta.url)));
  const {call}=app();
  for(const p of seed.profiles){
    const actual=(await call('/api/book',undefined,p.token)).data,expected=baseline[p.token];
    // SQL leaves ordering unspecified when priority and timestamp are identical.
    actual.alerts.sort((a,b)=>a.id.localeCompare(b.id));expected.alerts.sort((a,b)=>a.id.localeCompare(b.id));
    assert.deepEqual(actual,expected);
  }
});
test('seed values, six named portfolios and scopes are preserved',async()=>{
  const a=app(),v=await a.view();assert.equal(Object.keys(v.accounts).length,6);assert.equal(v.accounts.personal.cash,106000);assert.equal(v.accounts.business.net_worth,1680000);
  const rm=await a.call('/api/portfolio?id='+hid,undefined,'demo-commercial');assert.equal(Object.keys(rm.data.accounts).length,3);assert.deepEqual(rm.data.family,[]);
  assert.equal((await a.call('/api/portfolio?id=nonexistent')).status,403);
});
test('multiple portfolio creation, separate balances and duplicate validation',async()=>{
  const a=app();let r=await a.call('/api/create-portfolio',{client:hid,name:'Travel',type:'personal',opening_cash:'100.25'});assert.equal(r.status,200);
  const pf=Object.values(r.data.accounts).find(r=>r.name==='Travel');assert.equal(pf.cash,100.25);assert.equal(r.data.accounts.personal.cash,106000);
  assert.equal((await a.call('/api/create-portfolio',{client:hid,name:'travel',type:'personal'})).status,400);
  assert.equal((await a.call('/api/create-portfolio',{client:hid,name:'Other',type:'business'},'demo-advisor')).status,403);
  assert.equal((await a.call('/api/create-portfolio',{client:hid,name:'Tiny',type:'personal',opening_cash:'0.001'})).status,400);
  assert.equal(Object.keys((await a.view()).accounts).length,7);
});
test('family transfers select source and preserve cent precision',async()=>{
  const a=app(),v=await a.view(),recipient=v.family[0].id;
  let r=await a.call('/api/family-transfer',{client:hid,account:'education',recipient,amount:'0.29'});assert.equal(r.status,200);assert.equal(r.data.accounts.education.cash,44999.71);assert.equal(r.data.accounts.personal.cash,106000);
  assert.equal((await a.call('/api/family-transfer',{client:hid,account:'business',recipient,amount:1})).status,400);
  assert.equal((await a.call('/api/family-transfer',{client:hid,account:'education',recipient,amount:50000})).status,409);
  assert.equal((await a.view()).accounts.education.cash,44999.71);
});
test('investments debit once and rejected actions leave ledger unchanged',async()=>{
  const a=app();let r=await a.call('/api/invest',{client:hid,account:'treasury',name:'Sample bond',kind:'Bonds',amount:1000});assert.equal(r.status,200);assert.equal(r.data.accounts.treasury.cash,174000);
  const before=a.env.DB.row.payload;
  assert.equal((await a.call('/api/invest',{client:hid,account:'treasury',name:'Too much',kind:'Bonds',amount:999999})).status,409);assert.equal(a.env.DB.row.payload,before);
});
test('advisor proposal requires owner approval; repeat approval fails',async()=>{
  const a=app();let r=await a.call('/api/invest',{client:hid,account:'retirement',name:'New proposal',kind:'Funds',amount:1000},'demo-advisor');assert.equal(r.status,200);assert.equal(r.data.accounts.retirement.cash,180000);
  const proposal=r.data.proposals.find(r=>r.name==='New proposal');r=await a.call('/api/proposal',{client:hid,id:proposal.id,status:'Approve'});assert.equal(r.data.accounts.retirement.cash,179000);
  assert.equal((await a.call('/api/proposal',{client:hid,id:proposal.id,status:'Approve'})).status,409);
});
test('sale credits selected destination once per business portfolio',async()=>{
  const a=app(),sale={client:hid,business_account:'expansion',personal_account:'education',status:'Completed',buyer:'Demo buyer',gross:100000,fees:1000,reserve:9000,ownership_sold:60};
  let r=await a.call('/api/business-sale',sale);assert.equal(r.status,200);assert.equal(r.data.accounts.education.cash,135000);assert.equal(r.data.accounts.expansion.cash,260000);
  assert.equal((await a.call('/api/business-sale',sale)).status,409);
  r=await a.call('/api/business-sale',{...sale,business_account:'treasury'});assert.equal(r.status,200);assert.equal(r.data.accounts.education.cash,225000);
  assert.equal((await a.call('/api/business-sale',{...sale,business_account:'personal'})).status,400);
  assert.ok((await a.call('/api/notifications',undefined,'demo-advisor')).data.alerts.some(r=>r.signal==='valuation_question'));
});
test('chat respects selected portfolio and user scope; persists history',async()=>{
  const a=app();let r=await a.call('/api/chat',{client:hid,account:'retirement',question:'Available cash?'});assert.equal(r.status,200);assert.match(r.data.answer,/180,000/);assert.equal(r.data.mode,'Account summary');assert.equal(r.data.ai_connected,false);
  r=await a.call('/api/chat?id='+hid+'&account=retirement');assert.equal(r.data.messages.length,2);
  assert.equal((await a.call('/api/chat',{client:hid,account:'retirement',question:'Cash?'},'demo-ma')).status,403);
  assert.equal((await a.call('/api/chat?id='+hid+'&account=personal',undefined,'demo-commercial')).status,403);
});
test('external AI consent, account isolation, fallback and no transaction tools',async()=>{
  let payload;
  const a=app({OPENAI_API_KEY:'test-only',OPENAI_MODEL:'configured-model',aiFetch:async(url,options)=>{payload=JSON.parse(options.body);return Response.json({output:[{type:'message',content:[{type:'output_text',text:'Your recorded retirement cash is $180,000.'}]}]});}});
  const body={client:hid,account:'retirement',question:'Cash?'};
  assert.equal((await a.call('/api/chat',body)).status,400);assert.equal(payload,undefined);
  let r=await a.call('/api/chat',{...body,share_with_ai:true});assert.equal(r.data.mode,'AI response');assert.equal(payload.store,false);assert.equal(payload.tools,undefined);assert.equal(JSON.parse(payload.input[0].content.split(': ').slice(1).join(': ')).id,'retirement');assert.ok(!JSON.stringify(payload).includes('Business operations'));
  a.env.aiFetch=async()=>{throw new Error('offline');};r=await a.call('/api/chat',{...body,share_with_ai:true});assert.match(r.data.mode,/AI unavailable/);
});
test('advisor messaging, scoped recipients, replies and alerts',async()=>{
  const a=app();let r=await a.call('/api/connect-advisor',{client:hid,account:'retirement',kind:'Message',body:'Discuss my goals',recipient:'u-commercial'});assert.equal(r.status,403);
  r=await a.call('/api/connect-advisor',{client:hid,account:'retirement',kind:'Message',body:'Discuss my goals',recipient:'u-advisor'});assert.equal(r.status,200);
  const requests=(await a.call('/api/advisor-requests?id='+hid,undefined,'demo-advisor')).data.requests;const message=requests.find(r=>r.body==='Discuss my goals');assert.ok(message);
  assert.equal((await a.call('/api/advisor-reply',{id:message.id,reply:'Yes'},'demo-commercial')).status,403);
  assert.equal((await a.call('/api/advisor-reply',{id:message.id,reply:'Let us meet'},'demo-advisor')).status,200);
  assert.equal((await a.call('/api/advisor-requests?id='+hid)).data.requests.find(r=>r.id===message.id).reply,'Let us meet');
});
test('revoked account permissions hide alerts and deny chat and advisor history',async()=>{
  const a=app(),v=await a.view(),m=v.members.find(r=>r.role==='advisor');assert.ok((await a.call('/api/notifications',undefined,'demo-advisor')).data.alerts.length);
  assert.equal((await a.call('/api/access',{client:hid,member:m.id,scopes:['summary']})).status,200);
  assert.equal((await a.call('/api/chat',{client:hid,account:'business',question:'Cash?'},'demo-advisor')).status,403);
  assert.equal((await a.call('/api/notifications',undefined,'demo-advisor')).data.alerts.filter(r=>r.client===hid).length,0);
  assert.deepEqual((await a.call('/api/advisor-requests?id='+hid,undefined,'demo-advisor')).data.requests,[]);
});
test('A/B/C/D onboarding, introductions and triggers preserve permissions',async()=>{
  const a=app();
  for(const [b,p,group] of [[true,true,'A'],[false,true,'B'],[true,false,'C'],[false,false,'D']]) {
    const r=await a.call('/api/onboard',{name:'Demo '+group,owner:'New owner',industry:'Demo',business_pnc:b,personal_pnc:p});assert.equal(r.status,200);
    const id=r.data.client;assert.equal((await a.call('/api/portfolio?id='+id)).data.group,group);
    assert.equal((await a.call('/api/introduction',{client:id,action:'request'},'demo-commercial')).status,200);
    assert.equal((await a.call('/api/introduction',{client:id,action:'approve'})).status,200);
    assert.equal((await a.call('/api/introduction',{client:id,action:'accept'},'demo-advisor')).status,200);
    const signal=seed.catalog.find(r=>group in r.priorities);
    assert.equal((await a.call('/api/signal',{client:id,signal:signal.id,source:'Demo',note:'Observed'})).status,200);
    const alerts=(await a.call('/api/notifications',undefined,'demo-advisor')).data.alerts.filter(r=>r.client===id);
    assert.ok(alerts.length>0);
    const count=alerts.length;await a.call('/api/signal',{client:id,signal:signal.id,source:'Second event',note:'Observed again'});
    assert.equal((await a.call('/api/notifications',undefined,'demo-advisor')).data.alerts.filter(r=>r.client===id).length,count+1);
  }
});
test('concurrent debits cannot overspend or overwrite changes',async()=>{
  const a=app();await a.view();
  const [r1,r2]=await Promise.all([1,2].map(i=>a.call('/api/invest',{client:hid,account:'education',amount:30000,name:'Concurrent '+i,kind:'Funds'})));
  assert.deepEqual([r1.status,r2.status].sort(),[200,409]);assert.equal((await a.view()).accounts.education.cash,15000);
});
test('permission change during AI request prevents saving or releasing stale answer',async()=>{
  let entered,release;const gate=new Promise(r=>release=r),ready=new Promise(r=>entered=r);
  const a=app({OPENAI_API_KEY:'test-only',OPENAI_MODEL:'configured-model',aiFetch:async()=>{entered();await gate;return Response.json({output:[{type:'message',content:[{type:'output_text',text:'Sensitive answer'}]}]});}});
  const v=await a.view(),m=v.members.find(r=>r.role==='advisor');
  const pending=a.call('/api/chat',{client:hid,account:'retirement',question:'Cash?',share_with_ai:true},'demo-advisor');await ready;
  await a.call('/api/access',{client:hid,member:m.id,scopes:['summary']});release();const r=await pending;assert.equal(r.status,409);assert.equal(r.data.answer,undefined);
  assert.equal(JSON.parse(a.env.DB.row.payload).portfolio_chat.length,0);
});
test('durable reload keeps new data instead of reseeding',async()=>{
  const a=app();await a.call('/api/create-portfolio',{client:hid,type:'business',name:'Persistent',opening_cash:50});const db=a.env.DB;
  const b=app({DB:db});assert.equal(Object.values((await b.view()).accounts).find(r=>r.name==='Persistent').cash,50);assert.equal(db.row.version,1);
});
test('invalid tokens, malformed JSON, methods and oversized bodies are rejected',async()=>{
  const a=app();assert.equal((await a.call('/api/book',undefined,'bad')).status,401);
  for(const [body,status] of [['{',400],['[]',400],['x'.repeat(100001),413]]){
    const r=await handle(new Request('https://test.invalid/api/invest',{method:'POST',headers:{Authorization:'Bearer demo-owner'},body}),a.env,seed);assert.equal(r.status,status);
  }
  assert.equal((await handle(new Request('https://test.invalid/api/book',{method:'DELETE',headers:{Authorization:'Bearer demo-owner'}}),a.env,seed)).status,405);
});
