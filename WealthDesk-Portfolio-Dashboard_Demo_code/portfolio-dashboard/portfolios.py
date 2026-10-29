"""Simple portfolio ledger and case-trigger notifications. No bank or broker execution."""
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
import json
import core as product
from signals import BY_ID,ROUTING
C=None

def cents(value):
    try:
        v=Decimal(str(value));product.require(v.is_finite() and v>=Decimal('0.01') and v<=Decimal('100000000000'),'Enter an amount from $0.01 to $100 billion')
        product.require(v==v.quantize(Decimal('0.01')),'Dollar amounts support at most two decimal places')
        return int(v*100)
    except (InvalidOperation,ValueError,TypeError):raise product.Problem('Enter a valid dollar amount')
def money(v):return v/100

def init(connect):
    global C;C=connect
    with C() as c:c.executescript('''CREATE TABLE IF NOT EXISTS named_portfolios(client TEXT,id TEXT,name TEXT,type TEXT,PRIMARY KEY(client,id));
CREATE TABLE IF NOT EXISTS portfolio_cash(client TEXT,account TEXT,balance INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(client,account));
    CREATE TABLE IF NOT EXISTS portfolio_assets(id TEXT PRIMARY KEY,client TEXT,account TEXT,name TEXT,kind TEXT,value INTEGER);
    CREATE TABLE IF NOT EXISTS portfolio_family(id TEXT PRIMARY KEY,client TEXT,name TEXT,relation TEXT,balance INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS portfolio_ledger(id TEXT PRIMARY KEY,client TEXT,account TEXT,kind TEXT,amount INTEGER,description TEXT,at TEXT);
    CREATE TABLE IF NOT EXISTS portfolio_proposals(id TEXT PRIMARY KEY,client TEXT,account TEXT,name TEXT,kind TEXT,amount INTEGER,status TEXT,by_user TEXT);
    CREATE TABLE IF NOT EXISTS portfolio_deals(id TEXT PRIMARY KEY,client TEXT,buyer TEXT,gross INTEGER,fees INTEGER,reserve INTEGER,ownership_sold REAL,status TEXT,at TEXT);
    CREATE TABLE IF NOT EXISTS portfolio_contacts(id TEXT PRIMARY KEY,user_id TEXT,name TEXT,kind TEXT,company TEXT,email TEXT,client TEXT);
    CREATE TABLE IF NOT EXISTS portfolio_alerts(id TEXT PRIMARY KEY,client TEXT,user_id TEXT,signal TEXT,event_key TEXT,priority INTEGER,title TEXT,body TEXT,domain TEXT,status TEXT,at TEXT,UNIQUE(user_id,event_key));''')
    with C() as c:
        cols={r['name'] for r in c.execute('PRAGMA table_info(portfolio_deals)')}
        for key,default in [('business_account','business'),('personal_account','personal')]:
            if key not in cols:c.execute(f"ALTER TABLE portfolio_deals ADD COLUMN {key} TEXT DEFAULT '{default}'")

def ensure_accounts(c,hid):
    for aid,name,kind in [('personal','Everyday personal','personal'),('business','Business operations','business')]:c.execute('INSERT OR IGNORE INTO named_portfolios VALUES(?,?,?,?)',(hid,aid,name,kind))

def account_info(c,hid,aid):
    ensure_accounts(c,hid);r=c.execute('SELECT * FROM named_portfolios WHERE client=? AND id=?',(hid,aid)).fetchone();product.require(r is not None,'Portfolio not found',404);return dict(r)

def account_type(c,hid,aid):return account_info(c,hid,aid)['type']

def permissions(c,u,hid,account):
    product.access(c,u,hid)
    kind=account_type(c,hid,account)
    return product.access(c,u,hid,'planning' if kind=='personal' else 'financial')

def balance(c,hid,account):
    c.execute('INSERT OR IGNORE INTO portfolio_cash VALUES(?,?,0)',(hid,account));return c.execute('SELECT balance FROM portfolio_cash WHERE client=? AND account=?',(hid,account)).fetchone()['balance']
def ledger(c,hid,account,kind,amount,description):
    c.execute('INSERT INTO portfolio_ledger VALUES(?,?,?,?,?,?,?)',(product.ident(),hid,account,kind,amount,description,product.now()))
def debit(c,hid,account,amount):
    product.require(balance(c,hid,account)>=amount,'Insufficient recorded cash. Add the actual account balance or sale proceeds first.',409)
    c.execute('UPDATE portfolio_cash SET balance=balance-? WHERE client=? AND account=?',(amount,hid,account))
def credit(c,hid,account,amount):
    balance(c,hid,account);c.execute('UPDATE portfolio_cash SET balance=balance+? WHERE client=? AND account=?',(amount,hid,account))
def buy(c,hid,account,name,kind,amount):
    debit(c,hid,account,amount);c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(product.ident(),hid,account,name,kind,amount));ledger(c,hid,account,'Investment',-amount,name)

def emit(c,hid,sid,event_key):
    p=product.load(c,hid);s=BY_ID[sid];priority=s['priorities'].get(p['group'],3)
    if p['group']=='A':
        observed={r['signal'] for r in c.execute('SELECT signal FROM signal_events WHERE client=?',(hid,))}
        if 'trust' in observed and any(BY_ID[x]['domain']=='business' for x in observed):priority=1
    lead=ROUTING[p['group']]['lead'];targets={lead}
    if p['group']=='A':targets.add('commercial')
    if p['group']=='C':targets|={'advisor','ma'}
    if sid in ('sale_tax','charitable','trust','qoe','distribution'):targets.add('cpa')
    if sid in ('trust','charitable','deal_lawyer','change_control','restructure','beneficiary'):targets.add('legal')
    if sid in ('ma_payment','data_room','buyer_offer','valuation_question','valuation_firm','relative_offer','referral'):targets.add('ma')
    for m in c.execute('SELECT * FROM membership WHERE client=? AND active=1',(hid,)):
        scopes=json.loads(m['scopes'])
        if m['role'] not in targets or 'summary' not in scopes:continue
        if s['domain']=='business' and 'financial' not in scopes:continue
        if s['domain']=='personal' and 'planning' not in scopes:continue
        c.execute('INSERT OR IGNORE INTO portfolio_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(product.ident(),hid,m['user_id'],sid,event_key,priority,p['name']+': '+s['label'],ROUTING[p['group']]['next']+' Possible transition; confirm with the owner.',s['domain'],'New',product.now()))

def dispatch(hid):
    with C() as c:
        for r in c.execute('SELECT id,signal FROM signal_events WHERE client=?',(hid,)).fetchall():emit(c,hid,r['signal'],r['id'])

def alerts(u):
    out=[]
    with C() as c:
        for r in c.execute('SELECT * FROM portfolio_alerts WHERE user_id=? ORDER BY priority,at DESC',(u['id'],)):
            try:scopes=product.access(c,u,r['client'])
            except product.Problem:continue
            if r['domain']=='business' and 'financial' not in scopes:continue
            if r['domain']=='personal' and 'planning' not in scopes:continue
            out.append(dict(r))
    return out

def view(u,hid):
    with C() as c:
        scopes=product.access(c,u,hid);p=product.load(c,hid);accounts={}
        ensure_accounts(c,hid)
        for spec in c.execute('SELECT * FROM named_portfolios WHERE client=? ORDER BY rowid',(hid,)).fetchall():
            a=spec['id'];scope='planning' if spec['type']=='personal' else 'financial'
            if scope not in scopes:continue
            cash=balance(c,hid,a);assets=[dict(r) for r in c.execute('SELECT * FROM portfolio_assets WHERE client=? AND account=?',(hid,a))]
            for asset in assets:asset['value']=money(asset['value'])
            liabilities=sum(v['value'] for v in assets if v['kind']=='Liability');investments=sum(v['value'] for v in assets if v['kind'] not in ('Liability','Property','Equipment','Other asset'))
            accounts[a]={'id':a,'name':spec['name'],'type':spec['type'],'currency':'USD','cash_recorded':c.execute("SELECT 1 FROM portfolio_ledger WHERE client=? AND account=? AND kind IN ('Opening balance','Deposit','Withdrawal','Investment','Business sale proceeds','Family transfer')",(hid,a)).fetchone() is not None,'cash':money(cash),'assets':assets,'liabilities':liabilities,'investments':investments,'net_worth':money(cash)+sum(v['value'] for v in assets if v['kind']!='Liability')-liabilities}
        family=[{**dict(r),'balance':money(r['balance'])} for r in c.execute('SELECT * FROM portfolio_family WHERE client=?',(hid,))] if 'family' in scopes else []
        proposals=[{**dict(r),'amount':money(r['amount'])} for r in c.execute('SELECT * FROM portfolio_proposals WHERE client=?',(hid,)) if r['account'] in accounts]
        history=[{**dict(r),'amount':money(r['amount'])} for r in c.execute('SELECT * FROM portfolio_ledger WHERE client=? ORDER BY at DESC,rowid DESC LIMIT 80',(hid,)) if r['account'] in accounts]
        deals=[{**dict(r),**{k:money(r[k]) for k in ('gross','fees','reserve')}} for r in c.execute('SELECT * FROM portfolio_deals WHERE client=? ORDER BY at DESC',(hid,))] if 'financial' in scopes or 'planning' in scopes else []
        detection=product.detection(c,hid,p,scopes) if u['role']!='family' else None
        return {'id':hid,'name':p['name'],'owner':p['owner'],'group':p['group'],'accounts':accounts,'family':family,'proposals':proposals,'history':history,'deals':deals,'members':product.member_view(c,hid),'scopes':scopes,'introduction':p['intro_status'],'detection':detection,'demo':p.get('demo',False)}

def book(u):
    ws=product.workspace(u);rows=[]
    for case in ws['cases']:
        item=view(u,case['id']);rows.append({k:item[k] for k in ('id','name','owner','group','accounts','introduction','detection','demo')})
    with C() as c:contacts=[dict(r) for r in c.execute('SELECT * FROM portfolio_contacts WHERE user_id=?',(u['id'],))]
    return {'user':ws['user'],'clients':rows,'contacts':contacts,'alerts':alerts(u),'catalog':ws['catalog'],'demo':any(r['demo'] for r in rows)}

def post(u,path,d):
    if path=='/api/contact':
        product.rolecheck(u,{'advisor','commercial'});kind=product.text(d,'kind',50);product.require(kind in ('Business owner','Broker','CA','Attorney','Other'),'Choose a client/contact type')
        with C() as c:c.execute('INSERT INTO portfolio_contacts VALUES(?,?,?,?,?,?,?)',(product.ident(),u['id'],product.text(d,'name',100),kind,product.text(d,'company',100,default='Independent'),d.get('email','')[:200],d.get('client','')[:100]))
        return {'saved':True}
    if path=='/api/alert-status':
        status=product.text(d,'status',30);product.require(status in ('New','Reviewing','Resolved'),'Invalid status')
        with C() as c:c.execute('UPDATE portfolio_alerts SET status=? WHERE id=? AND user_id=?',(status,d.get('id'),u['id']))
        return {'saved':True}
    hid=product.text(d,'client',100)
    with C() as c:
        c.execute('BEGIN IMMEDIATE');product.access(c,u,hid)
        if path=='/api/create-portfolio':
            product.rolecheck(u,{'owner'});ensure_accounts(c,hid);kind=d.get('type');product.require(kind in ('personal','business'),'Choose personal or business')
            name=product.text(d,'name',80);product.require(c.execute('SELECT 1 FROM named_portfolios WHERE client=? AND type=? AND lower(name)=lower(?)',(hid,kind,name)).fetchone() is None,'A portfolio with that name already exists')
            aid='pf-'+product.ident();c.execute('INSERT INTO named_portfolios VALUES(?,?,?,?)',(hid,aid,name,kind))
            initial=d.get('opening_cash')
            if initial not in (None,'',0,'0'):
                amount=cents(initial);credit(c,hid,aid,amount);ledger(c,hid,aid,'Opening balance',amount,'Portfolio opening balance')
        elif path=='/api/family-recipient':
            product.rolecheck(u,{'owner'});c.execute('INSERT INTO portfolio_family VALUES(?,?,?,?,0)',(product.ident(),hid,product.text(d,'name',100),product.text(d,'relation',100)))
        elif path=='/api/cash-entry':
            product.rolecheck(u,{'owner'});a=d.get('account');permissions(c,u,hid,a);amount=cents(d.get('amount'));kind=d.get('kind','Opening balance')
            product.require(kind in ('Opening balance','Deposit','Withdrawal'),'Invalid entry type')
            if kind=='Opening balance':product.require(c.execute("SELECT 1 FROM portfolio_ledger WHERE client=? AND account=? AND kind IN ('Opening balance','Deposit','Withdrawal','Investment','Business sale proceeds','Family transfer')",(hid,a)).fetchone() is None,'Opening balance already recorded; use deposits or withdrawals',409)
            if kind=='Withdrawal':debit(c,hid,a,amount);amount=-amount
            else:credit(c,hid,a,amount)
            ledger(c,hid,a,kind,amount,product.text(d,'description',300,default=kind))
        elif path=='/api/family-transfer':
            product.rolecheck(u,{'owner'});a=d.get('account','personal');permissions(c,u,hid,a);product.require(account_type(c,hid,a)=='personal','Family transfers must use a personal portfolio');amount=cents(d.get('amount'));recipient=c.execute('SELECT * FROM portfolio_family WHERE id=? AND client=?',(d.get('recipient'),hid)).fetchone();product.require(recipient is not None,'Choose a family recipient')
            debit(c,hid,a,amount);c.execute('UPDATE portfolio_family SET balance=balance+? WHERE id=?',(amount,recipient['id']));ledger(c,hid,a,'Family transfer',-amount,recipient['name']+' · '+product.text(d,'note',200,default='Family support'))
        elif path=='/api/asset':
            product.rolecheck(u,{'owner'});a=d.get('account');permissions(c,u,hid,a);kind=product.text(d,'kind',50);product.require(kind in ('Equities','Funds','Bonds','Deposit','Property','Equipment','Other asset','Liability'),'Choose a valid asset type')
            amount=cents(d.get('amount'));c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(product.ident(),hid,a,product.text(d,'name',100),kind,amount));ledger(c,hid,a,'Holding recorded',0,product.text(d,'name',100))
        elif path=='/api/asset-value':
            product.rolecheck(u,{'owner'});r=c.execute('SELECT * FROM portfolio_assets WHERE id=? AND client=?',(d.get('asset'),hid)).fetchone();product.require(r is not None,'Holding not found',404);permissions(c,u,hid,r['account']);amount=cents(d.get('amount'));c.execute('UPDATE portfolio_assets SET value=? WHERE id=?',(amount,r['id']));ledger(c,hid,r['account'],'Value updated',0,r['name'])
        elif path=='/api/invest':
            product.rolecheck(u,{'owner','advisor'});a=d.get('account');permissions(c,u,hid,a);amount=cents(d.get('amount'));name=product.text(d,'name',100);kind=product.text(d,'kind',50);product.require(kind in ('Equities','Funds','Bonds','Deposit'),'Choose an investment category')
            if u['role']=='advisor':c.execute('INSERT INTO portfolio_proposals VALUES(?,?,?,?,?,?,?,?)',(product.ident(),hid,a,name,kind,amount,'Awaiting owner approval',u['id']))
            else:buy(c,hid,a,name,kind,amount)
        elif path=='/api/proposal':
            product.rolecheck(u,{'owner'});r=c.execute('SELECT * FROM portfolio_proposals WHERE id=? AND client=?',(d.get('id'),hid)).fetchone();product.require(r is not None and r['status']=='Awaiting owner approval','Proposal is not awaiting approval',409)
            status=d.get('status');product.require(status in ('Approve','Decline'),'Choose approve or decline')
            if status=='Approve':buy(c,hid,r['account'],r['name'],r['kind'],r['amount'])
            c.execute('UPDATE portfolio_proposals SET status=? WHERE id=?',('Recorded' if status=='Approve' else 'Declined',r['id']))
        elif path=='/api/business-sale':
            product.rolecheck(u,{'owner'});source=d.get('business_account','business');target=d.get('personal_account','personal');permissions(c,u,hid,source);permissions(c,u,hid,target);product.require(account_type(c,hid,source)=='business' and account_type(c,hid,target)=='personal','Choose a business source and personal destination');status=d.get('status');product.require(status in ('Considering','Offer received','Completed'),'Choose a sale status')
            buyer=product.text(d,'buyer',100);gross=cents(d.get('gross'));fees=0 if d.get('fees') in (0,'0',None,'') else cents(d.get('fees'));reserve=0 if d.get('reserve') in (0,'0',None,'') else cents(d.get('reserve'));pct=product.number(d.get('ownership_sold'),'ownership_sold',.01,100)
            product.require(fees+reserve<=gross,'Fees and reserve exceed owner proceeds')
            if status=='Completed':
                # Only one recorded closing in this simple owner portfolio; repeat submit cannot double-credit.
                product.require(c.execute('SELECT 1 FROM portfolio_deals WHERE client=? AND business_account=? AND status=?',(hid,source,'Completed')).fetchone() is None,'A sale closing has already been recorded',409)
                credit(c,hid,target,gross-fees-reserve);ledger(c,hid,target,'Business sale proceeds',gross-fees-reserve,buyer+' · net owner proceeds; business-account assets unchanged')
            c.execute('INSERT INTO portfolio_deals(id,client,buyer,gross,fees,reserve,ownership_sold,status,at,business_account,personal_account) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(product.ident(),hid,buyer,gross,fees,reserve,pct,status,product.now(),source,target))
            p=product.load(c,hid);sid='buyer_offer' if p['group']=='C' else 'valuation_question' if p['group']=='A' else 'sale_tax' if p['group']=='B' else 'family_sale'
            eid=product.ident();c.execute('INSERT INTO signal_events VALUES(?,?,?,?,?,?,?)',(eid,hid,sid,'Owner-entered sale update',product.now(),'Owner reported '+status,u['id']));emit(c,hid,sid,eid)
        else:raise product.Problem('Not found',404)
        product.event(c,hid,u['name'],'Portfolio update',path.rsplit('/',1)[-1])
    return view(u,hid)
