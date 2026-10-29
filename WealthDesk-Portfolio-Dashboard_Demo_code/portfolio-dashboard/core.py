"""Portfolio membership and signal routing. No dependency on the earlier project."""
import json,math,secrets,uuid
from datetime import datetime,timezone
from signals import CATALOG,BY_ID,ROUTING
C=None
ROLES={'owner':'Business owner','advisor':'Wealth advisor','commercial':'Commercial RM','ma':'Broker','cpa':'CA','legal':'Attorney'}
SCOPES=['summary','planning','financial','family']
class Problem(Exception):
    def __init__(self,message,status=400):self.message=message;self.status=status

def require(ok,message,status=400):
    if not ok:raise Problem(message,status)
def text(d,key,limit=1000,default=None):
    value=d.get(key,default);require(isinstance(value,str) and 0<len(value.strip())<=limit,f'{key} is required (maximum {limit} characters)');return value.strip()
def number(value,name,lo=0,hi=100000):
    require(type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi,f'{name} must be between {lo} and {hi}');return float(value)
def ident():return uuid.uuid4().hex[:16]
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def encode(d):return json.dumps(d,allow_nan=False)
def rolecheck(u,roles):require(u['role'] in roles,'This action is not available to your role',403)
def init(connect):
    global C;C=connect
    with C() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,payload TEXT);
        CREATE TABLE IF NOT EXISTS identities(token TEXT PRIMARY KEY,id TEXT,name TEXT,role TEXT);
        CREATE TABLE IF NOT EXISTS membership(id TEXT PRIMARY KEY,client TEXT,user_id TEXT,role TEXT,name TEXT,scopes TEXT,active INTEGER);
        CREATE TABLE IF NOT EXISTS signal_events(id TEXT PRIMARY KEY,client TEXT,signal TEXT,source TEXT,observed TEXT,note TEXT,created_by TEXT);
        CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY,client TEXT,at TEXT,actor TEXT,action TEXT,detail TEXT);''')
        for role,name in ROLES.items():c.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?,?)',('demo-'+role,'u-'+role,name,role))
def auth(token):
    with C() as c:r=c.execute('SELECT * FROM identities WHERE token=?',(token,)).fetchone()
    require(r is not None,'Open a valid account session',401);return dict(r)
def load(c,hid):
    r=c.execute('SELECT payload FROM clients WHERE id=?',(hid,)).fetchone();require(r is not None,'Portfolio not found',404);return json.loads(r['payload'])
def save(c,hid,p):c.execute('UPDATE clients SET payload=? WHERE id=?',(encode(p),hid))
def event(c,hid,actor,action,detail=''):c.execute('INSERT INTO activity(client,at,actor,action,detail) VALUES(?,?,?,?,?)',(hid,now(),actor,action,detail))
def access(c,u,hid,scope='summary'):
    m=c.execute('SELECT * FROM membership WHERE client=? AND user_id=? AND active=1',(hid,u['id'])).fetchone();require(m is not None,'This portfolio is not assigned to you',403)
    scopes=json.loads(m['scopes']);require(scope in scopes,'The owner has not shared this account with you',403);return scopes
def member_view(c,hid):return [{**{k:r[k] for k in ('id','user_id','name','role')},'scopes':json.loads(r['scopes']),'active':bool(r['active'])} for r in c.execute('SELECT * FROM membership WHERE client=?',(hid,))]
def workspace(u):
    with C() as c:
        cases=[{'id':r['client'],**load(c,r['client'])} for r in c.execute('SELECT client FROM membership WHERE user_id=? AND active=1',(u['id'],))]
    return {'user':{k:u[k] for k in ('id','name','role')},'cases':cases,'catalog':CATALOG}
def detection(c,hid,p,scopes):
    events=[dict(r) for r in c.execute('SELECT * FROM signal_events WHERE client=?',(hid,)) if BY_ID[r['signal']]['domain'] in ('public','referral') or (BY_ID[r['signal']]['domain']=='business' and 'financial' in scopes) or (BY_ID[r['signal']]['domain']=='personal' and 'planning' in scopes)]
    priority=min([BY_ID[r['signal']]['priorities'].get(p['group'],3) for r in events]+[3]);ids={r['signal'] for r in events}
    if p['group']=='A' and 'trust' in ids and any(BY_ID[i]['domain']=='business' for i in ids):priority=1
    return {'priority':priority,'priority_label':{1:'Act now',2:'Act soon',3:'Monitor'}[priority],'routing':ROUTING[p['group']],'signals':events}
def onboard(u,d):
    rolecheck(u,{'owner','commercial'});name=text(d,'name',100);owner=text(d,'owner',100)
    b=d.get('business_pnc');p=d.get('personal_pnc');require(type(b)==bool and type(p)==bool,'Select banking relationships')
    group={(True,True):'A',(False,True):'B',(True,False):'C',(False,False):'D'}[(b,p)]
    hid='p-'+ident();uid=u['id'] if u['role']=='owner' else 'u-'+ident();token=u['token'] if u['role']=='owner' else secrets.token_urlsafe(32)
    with C() as c:
        c.execute('INSERT INTO clients VALUES(?,?)',(hid,encode(dict(name=name,owner=owner,group=group,intro_status='Not requested',industry=text(d,'industry',100)))))
        c.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?,?)',(token,uid,owner,'owner'))
        c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,?)',(ident(),hid,uid,'owner',owner,encode(SCOPES),1))
        c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,?)',(ident(),hid,'u-commercial','commercial','Commercial RM',encode(['summary','financial']),1))
        event(c,hid,owner,'Portfolio created')
    return {'client':hid,'owner_token':token}
def post(u,path,d):
    if path=='/api/onboard':return onboard(u,d)
    hid=text(d,'client',100)
    with C() as c:
        c.execute('BEGIN IMMEDIATE');scopes=access(c,u,hid);p=load(c,hid)
        if path=='/api/invite':
            rolecheck(u,{'owner'});role=text(d,'role',30);require(role in ROLES and role!='owner','Choose an advisor or professional role')
            grant=d.get('scopes');require(isinstance(grant,list) and 'summary' in grant and all(s in SCOPES for s in grant),'Choose valid account permissions')
            name=text(d,'name',100);uid='u-'+role if d.get('use_existing') is True else 'u-'+ident();token='demo-'+role if d.get('use_existing') is True else secrets.token_urlsafe(32)
            existing=c.execute('SELECT id FROM membership WHERE client=? AND user_id=?',(hid,uid)).fetchone()
            if existing:
                c.execute('UPDATE membership SET active=1,scopes=?,name=? WHERE id=?',(encode(grant),name,existing['id']));return {'token':token,'name':name}
            c.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?,?)',(token,uid,name,role));c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,?)',(ident(),hid,uid,role,name,encode(grant),1))
            return {'token':token,'name':name}
        if path=='/api/access':
            rolecheck(u,{'owner'});r=c.execute('SELECT * FROM membership WHERE id=? AND client=?',(d.get('member'),hid)).fetchone();require(r is not None and r['role']!='owner','Member not found')
            grant=d.get('scopes',[]);require(isinstance(grant,list) and all(s in SCOPES for s in grant) and (not grant or 'summary' in grant),'Invalid permissions')
            c.execute('UPDATE membership SET active=?,scopes=? WHERE id=?',(int(bool(grant)),encode(grant),r['id']))
        elif path=='/api/signal':
            sid=text(d,'signal',100);require(sid in BY_ID and p['group'] in BY_ID[sid]['priorities'],'Choose a relevant observed signal')
            domain=BY_ID[sid]['domain']
            if domain=='business':access(c,u,hid,'financial')
            if domain=='personal':access(c,u,hid,'planning')
            c.execute('INSERT INTO signal_events VALUES(?,?,?,?,?,?,?)',(ident(),hid,sid,text(d,'source',200),now(),text(d,'note',1000),u['id']))
        elif path=='/api/introduction':
            a=d.get('action')
            if a=='request':rolecheck(u,{'commercial','advisor'});p['intro_status']='Awaiting owner approval'
            elif a=='approve':
                rolecheck(u,{'owner'});require(p['intro_status']=='Awaiting owner approval','A request is required first')
                grant=encode(['summary','planning','financial']);m=c.execute('SELECT id FROM membership WHERE client=? AND user_id=?',(hid,'u-advisor')).fetchone()
                if m:c.execute('UPDATE membership SET active=1,scopes=? WHERE id=?',(grant,m['id']))
                else:c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,?)',(ident(),hid,'u-advisor','advisor','Wealth advisor',grant,1))
                p['intro_status']='Approved'
            elif a=='accept':rolecheck(u,{'advisor'});require(p['intro_status']=='Approved','Owner approval is required');p['intro_status']='Accepted'
            else:raise Problem('Invalid introduction action')
            save(c,hid,p)
        else:raise Problem('Not found',404)
        event(c,hid,u['name'],path.rsplit('/',1)[-1])
    return {'saved':True}
