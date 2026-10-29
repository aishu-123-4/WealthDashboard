import os
from unittest.mock import patch
from helpers import HTTPTestCase
import app,core,portfolios

class MultiplePortfoliosTests(HTTPTestCase):
 def add(self,hid,name,kind,opening=''):
  code,out=self.call('create-portfolio',data=dict(client=hid,name=name,type=kind,opening_cash=opening));self.assertEqual(code,200,out)
  return next(a['id'] for a in out['accounts'].values() if a['name']==name)
 def test_create_named_portfolios_and_keep_balances_separate(self):
  hid=self.create();a=self.add(hid,'Retirement','personal',1000);b=self.add(hid,'Education','personal',2000);biz=self.add(hid,'Business reserve','business',3000)
  out=self.call('portfolio?id='+hid)[1];self.assertEqual(len(out['accounts']),5);self.assertEqual(out['accounts'][a]['cash'],1000)
  self.call('invest',data=dict(client=hid,account=a,name='Test investment',kind='Funds',amount=100))
  out=self.call('portfolio?id='+hid)[1];self.assertEqual(out['accounts'][a]['cash'],900);self.assertEqual(out['accounts'][b]['cash'],2000);self.assertEqual(out['accounts'][biz]['cash'],3000)
  self.assertEqual(self.call('create-portfolio',data=dict(client=hid,name='retirement',type='personal'))[0],400)
 def test_family_transfer_uses_selected_personal_portfolio(self):
  hid=self.create();a=self.add(hid,'Family support','personal',1000);b=self.add(hid,'Business reserve','business',1000)
  r=self.call('family-recipient',data=dict(client=hid,name='Test recipient',relation='Daughter'))[1]['family'][0]['id']
  out=self.call('family-transfer',data=dict(client=hid,account=a,recipient=r,amount=100))[1]
  self.assertEqual(out['accounts'][a]['cash'],900);self.assertEqual(out['accounts']['personal']['cash'],0)
  self.assertEqual(self.call('family-transfer',data=dict(client=hid,account=b,recipient=r,amount=100))[0],400)
 def test_sale_routes_to_selected_personal_portfolio_and_is_once_per_business(self):
  hid=self.create();a=self.add(hid,'Sale proceeds','personal');b=self.add(hid,'Second business portfolio','business')
  d=dict(client=hid,business_account=b,personal_account=a,buyer='Test buyer',gross=10000,fees=100,reserve=900,ownership_sold=100,status='Completed')
  code,out=self.call('business-sale',data=d);self.assertEqual(code,200,out);self.assertEqual(out['accounts'][a]['cash'],9000);self.assertEqual(out['accounts']['personal']['cash'],0)
  self.assertEqual(self.call('business-sale',data=d)[0],409)
  d['business_account']='business';self.assertEqual(self.call('business-sale',data=d)[0],200)
 def test_named_portfolio_permissions_chat_and_advisor_requests(self):
  hid=self.create();a=self.add(hid,'Private retirement','personal',1000);self.invite(hid,'cpa',['summary','financial'])
  self.assertNotIn(a,self.call('portfolio?id='+hid,'cpa')[1]['accounts'])
  self.assertEqual(self.call('chat','cpa',dict(client=hid,account=a,question='Cash?'))[0],403)
  self.invite(hid,'advisor',['summary','planning','financial'])
  self.assertEqual(self.call('chat',data=dict(client=hid,account=a,question='How much cash?'))[0],200)
  self.assertEqual(self.call('connect-advisor',data=dict(client=hid,account=a,recipient='u-advisor',kind='Message',body='Test request'))[0],200)
  self.assertEqual(len(self.call('advisor-requests?id='+hid,'advisor')[1]['requests']),1)
 def test_demo_seed_is_populated_and_does_not_reset_edits(self):
  with patch.dict(os.environ,{'PORTFOLIO_DEMO':'1'}):
   app.init();owner=core.auth('demo-owner');b=portfolios.book(owner)
   demo=next(c for c in b['clients'] if c['id']=='demo-mehta');self.assertEqual(len(demo['accounts']),6)
   self.assertEqual(sum(a['type']=='personal' for a in demo['accounts'].values()),3)
   for who in ['advisor','cpa','ma','commercial']:
    book=portfolios.book(core.auth('demo-'+who));self.assertEqual(len(book['clients']),3);self.assertTrue(book['alerts'])
   portfolios.post(owner,'/api/cash-entry',dict(client='demo-mehta',account='personal',kind='Deposit',amount=12,description='Test deposit'))
   before=portfolios.view(owner,'demo-mehta')['accounts']['personal']['cash'];app.init()
   self.assertEqual(portfolios.view(owner,'demo-mehta')['accounts']['personal']['cash'],before)
   self.assertEqual(len(self.call('profiles')[1]['profiles']),7)
