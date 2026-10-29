"""Explicitly fictional demonstration data, enabled by the owner's demo request."""
import json
import core,portfolios,chat
PROFILES=[
 {'token':'demo-owner','name':'Anita Mehta · Business owner','role':'owner','person':'Anita Mehta'},
 {'token':'demo-owner-james','name':'James Carter · Business owner','role':'owner','person':'James Carter'},
 {'token':'demo-owner-maya','name':'Maya Rao · Business owner','role':'owner','person':'Maya Rao'},
 {'token':'demo-advisor','name':'Sarah Williams · Wealth advisor','role':'advisor','person':'Sarah Williams'},
 {'token':'demo-cpa','name':'Priya Shah · CA','role':'cpa','person':'Priya Shah'},
 {'token':'demo-ma','name':'David Chen · Broker','role':'ma','person':'David Chen'},
 {'token':'demo-commercial','name':'Michael Reed · Commercial RM','role':'commercial','person':'Michael Reed'}]

def seed(connect):
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS demo_versions(version TEXT PRIMARY KEY)')
        if c.execute('SELECT 1 FROM demo_versions WHERE version=?',('multi-portfolios-v1',)).fetchone():return
        for p in PROFILES:
            uid='u-'+p['token'].removeprefix('demo-')
            c.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?,?)',(p['token'],uid,p['person'],p['role']))
            c.execute('UPDATE identities SET name=? WHERE token=?',(p['person'],p['token']))
        cases=[('demo-mehta','Mehta Manufacturing','Anita Mehta','A','u-owner'),('demo-riverbend','Riverbend Foods','James Carter','C','u-owner-james'),('demo-oak','Oak & Thread Retail','Maya Rao','B','u-owner-maya')]
        for hid,name,owner,group,uid in cases:
            if c.execute('SELECT 1 FROM clients WHERE id=?',(hid,)).fetchone():continue
            c.execute('INSERT INTO clients VALUES(?,?)',(hid,core.encode(dict(name=name,owner=owner,group=group,intro_status='Accepted',industry='Sample business',demo=True))))
            c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,1)',(core.ident(),hid,uid,'owner',owner,core.encode(core.SCOPES)))
            for p in PROFILES:
                if p['role']=='owner':continue
                scopes=['summary','financial']+(['planning'] if p['role'] in ('advisor','cpa') else [])
                c.execute('INSERT INTO membership VALUES(?,?,?,?,?,?,1)',(core.ident(),hid,'u-'+p['role'],p['role'],p['person'],core.encode(scopes)))
            portfolios.ensure_accounts(c,hid)
            amount=125000 if hid=='demo-mehta' else 80000
            for aid,opening in [('personal',amount),('business',420000 if hid=='demo-mehta' else 250000)]:
                portfolios.credit(c,hid,aid,int(opening*100));portfolios.ledger(c,hid,aid,'Opening balance',int(opening*100),'Fictional demo opening balance')
            c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(core.ident(),hid,'personal','Diversified equity fund','Funds',22500000))
            c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(core.ident(),hid,'personal','Investment-grade bonds','Bonds',8500000))
            for title,kind,value in [('Operating equipment','Equipment',54000000),('Business premises','Property',90000000),('Working-capital loan','Liability',18000000)]:c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(core.ident(),hid,'business',title,kind,value))
            if hid=='demo-mehta':
                extras=[('retirement','Retirement & long-term wealth','personal',180000),('education','Children’s education','personal',45000),('expansion','Expansion & growth','business',260000),('treasury','Business treasury reserve','business',175000)]
                for aid,title,kind,opening in extras:
                    c.execute('INSERT INTO named_portfolios VALUES(?,?,?,?)',(hid,aid,title,kind));portfolios.credit(c,hid,aid,opening*100);portfolios.ledger(c,hid,aid,'Opening balance',opening*100,'Fictional demo opening balance')
                    c.execute('INSERT INTO portfolio_assets VALUES(?,?,?,?,?,?)',(core.ident(),hid,aid,'Long-term fund' if kind=='personal' else 'Treasury investment','Funds' if kind=='personal' else 'Bonds',35000000 if aid=='retirement' else 12000000))
                for name,relation,amount in [('Rahul Mehta','Spouse',12000),('Riya Mehta','Daughter',4000),('Arjun Mehta','Son',3000)]:
                    c.execute('INSERT INTO portfolio_family VALUES(?,?,?,?,?)',(core.ident(),hid,name,relation,amount*100));portfolios.debit(c,hid,'personal',amount*100);portfolios.ledger(c,hid,'personal','Family transfer',-amount*100,name+' · fictional demo family support')
                c.execute('INSERT INTO portfolio_proposals VALUES(?,?,?,?,?,?,?,?)',(core.ident(),hid,'retirement','Diversified bond allocation','Bonds',2500000,'Awaiting owner approval','u-advisor'))
                c.execute('INSERT INTO portfolio_deals(id,client,buyer,gross,fees,reserve,ownership_sold,status,at,business_account,personal_account) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(core.ident(),hid,'Sample strategic buyer',320000000,9600000,64000000,70,'Offer received',core.now(),'business','retirement'))
                request_id=core.ident()
                c.execute('INSERT INTO advisor_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',(request_id,hid,'u-owner','u-advisor','retirement','Meeting request','Demo: I would like to discuss how a possible business sale changes my retirement portfolio.','2026-11-10T14:00','New','',core.now()))
                c.execute('INSERT INTO portfolio_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(core.ident(),hid,'u-advisor','advisor_request',request_id,2,'Anita Mehta: meeting request','Demo client requested a retirement planning discussion.','personal','New',core.now()))
            for sid in ({'A':['payoff','data_room','trust','qoe','valuation_question'],'C':['buyer_offer','ma_payment','short_credit'],'B':['sale_tax','charitable','retirement_plan']}[group]):
                eid=core.ident();c.execute('INSERT INTO signal_events VALUES(?,?,?,?,?,?,?)',(eid,hid,sid,'Fictional demo event',core.now(),'Sample observation for the demo only',uid));portfolios.emit(c,hid,sid,eid)
            core.event(c,hid,'Demo setup','Sample portfolio populated','Fictional data; no real customer accounts')
        # Professional contacts appear in the advisor's directory alongside authorized owners.
        for name,kind,company in [('David Chen','Broker','Harbor Business Sales'),('Priya Shah','CA','Shah Advisory'),('Michael Reed','Other','Commercial relationship management')]:c.execute('INSERT INTO portfolio_contacts VALUES(?,?,?,?,?,?,?)',(core.ident(),'u-advisor',name,kind,company,'','demo-mehta'))
        c.execute('INSERT INTO demo_versions VALUES(?)',('multi-portfolios-v1',))
