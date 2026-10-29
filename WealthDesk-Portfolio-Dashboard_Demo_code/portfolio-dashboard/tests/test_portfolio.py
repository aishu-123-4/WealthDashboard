"""Temporary fixtures for ledger, alerts, scoped chat and advisor requests."""
import json,os,unittest
from unittest.mock import patch
from helpers import HTTPTestCase
import chat as assistant_chat
import core as product

class PortfolioTests(HTTPTestCase):
    def fund(self,hid,a,amount):return self.call('cash-entry',data=dict(client=hid,account=a,amount=amount,kind='Opening balance',description='Test fixture opening'))
    def test_01_cash_family_transfer_and_insufficient_funds(self):
        hid=self.create();self.assertEqual(self.fund(hid,'personal',1000)[0],200)
        out=self.call('family-recipient',data=dict(client=hid,name='Test relative',relation='Spouse'))[1];rid=out['family'][0]['id']
        code,out=self.call('family-transfer',data=dict(client=hid,recipient=rid,amount=125.25,note='Test'));self.assertEqual(code,200,out);self.assertEqual(out['accounts']['personal']['cash'],874.75);self.assertEqual(out['family'][0]['balance'],125.25)
        self.assertEqual(self.call('family-transfer',data=dict(client=hid,recipient=rid,amount=1000))[0],409)
    def test_02_investments_proposals_and_idempotent_approval(self):
        hid=self.create();self.fund(hid,'personal',1000);self.invite(hid,'advisor',['summary','financial','planning'])
        code,out=self.call('invest','advisor',dict(client=hid,account='personal',name='Test fund',kind='Funds',amount=200));self.assertEqual(code,200,out);pid=out['proposals'][0]['id'];self.assertEqual(out['accounts']['personal']['cash'],1000)
        code,out=self.call('proposal',data=dict(client=hid,id=pid,status='Approve'));self.assertEqual(code,200,out);self.assertEqual(out['accounts']['personal']['cash'],800);self.assertEqual(out['accounts']['personal']['investments'],200)
        self.assertEqual(self.call('proposal',data=dict(client=hid,id=pid,status='Approve'))[0],409)
    def test_03_sale_proceeds_credit_personal_once_and_alert(self):
        hid=self.create();self.invite(hid,'advisor',['summary','planning','financial'])
        d=dict(client=hid,buyer='Test buyer',gross=5000,fees=100,reserve=900,ownership_sold=100,status='Completed')
        code,out=self.call('business-sale',data=d);self.assertEqual(code,200,out);self.assertEqual(out['accounts']['personal']['cash'],4000)
        self.assertEqual(self.call('business-sale',data=d)[0],409)
        alerts=self.call('notifications','advisor')[1]['alerts'];self.assertTrue(alerts);self.assertIn('Possible transition',alerts[0]['body'])
    def test_04_trigger_alerts_are_targeted_deduplicated_and_revocable(self):
        hid=self.create();self.invite(hid,'advisor',['summary','financial','planning'])
        self.call('signal',data=dict(client=hid,signal='payoff',source='Test evidence',note='Test'))
        aa=self.call('notifications','advisor')[1]['alerts'];self.assertEqual(len(aa),1);self.assertEqual(aa[0]['priority'],1)
        self.assertEqual(self.call('notifications','cpa')[1]['alerts'],[])
        m=next(m for m in self.detail(hid)[1]['members'] if m['role']=='advisor')
        self.call('access',data=dict(client=hid,member=m['id'],scopes=[]));self.assertEqual(self.call('notifications','advisor')[1]['alerts'],[])
    def test_05_chat_no_fake_ai_and_scope_checks(self):
        hid=self.create();self.fund(hid,'personal',1000)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            code,out=self.call('chat',data=dict(client=hid,account='personal',question='How much cash is available?'));self.assertEqual(code,200,out);self.assertEqual(out['mode'],'Account summary');self.assertIn('1,000.00',out['answer']);self.assertFalse(out['ai_connected'])
        self.invite(hid,'cpa',['summary','financial'])
        self.assertEqual(self.call('chat','cpa',dict(client=hid,account='personal',question='Tell me the cash'))[0],403)
        self.assertEqual(self.call('chat?id='+hid+'&account=personal','cpa')[0],403)
    def test_06_connected_ai_uses_only_selected_account_and_opt_in(self):
        hid=self.create();self.fund(hid,'personal',1000);self.fund(hid,'business',888888)
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'Test response from mocked provider.'}]}]}).encode()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'test-model'}),patch('chat.urllib.request.urlopen',return_value=Response()) as mocked:
            data=dict(client=hid,account='personal',question='Summarize my portfolio')
            with self.assertRaises(product.Problem):assistant_chat.ask(product.auth('demo-owner'),data)
            data['share_with_ai']=True;out=assistant_chat.ask(product.auth('demo-owner'),data);self.assertEqual(out['mode'],'AI response')
            payload=json.loads(mocked.call_args.args[0].data);self.assertFalse(payload['store']);self.assertNotIn('888888',json.dumps(payload));self.assertNotIn('tools',payload)
    def test_07_advisor_message_meeting_reply_and_inapp_alert(self):
        hid=self.create();self.invite(hid,'advisor',['summary','financial','planning'])
        d=dict(client=hid,account='personal',recipient='u-advisor',kind='Meeting request',body='Test meeting request',when='2026-11-03T12:00')
        code,out=self.call('connect-advisor',data=d);self.assertEqual(code,200,out)
        requests=self.call('advisor-requests?id='+hid,'advisor')[1]['requests'];self.assertEqual(len(requests),1)
        self.assertEqual(self.call('advisor-reply','commercial',dict(id=requests[0]['id'],reply='Wrong person'))[0],403)
        self.assertEqual(self.call('advisor-reply','advisor',dict(id=requests[0]['id'],reply='Test response'))[0],200)
        self.assertEqual(self.call('advisor-requests?id='+hid)[1]['requests'][0]['reply'],'Test response')
        self.assertTrue(self.call('notifications','advisor')[1]['alerts'])
    def test_08_existing_holdings_mark_and_contact_directory(self):
        hid=self.create();code,out=self.call('asset',data=dict(client=hid,account='business',name='Test equipment',kind='Equipment',amount=100));self.assertEqual(code,200,out)
        aid=out['accounts']['business']['assets'][0]['id'];out=self.call('asset-value',data=dict(client=hid,asset=aid,amount=150))[1];self.assertEqual(out['accounts']['business']['net_worth'],150)
        self.assertEqual(self.call('contact','advisor',dict(name='Test CA',kind='CA',company='Test practice',email='',client=''))[0],200)
        self.assertEqual(self.call('book','advisor')[1]['contacts'][0]['kind'],'CA')

    def test_09_owner_can_update_and_restore_advisor_access(self):
        hid=self.create();self.invite(hid,'advisor',['summary','financial'])
        self.assertNotIn('personal',self.call('portfolio?id='+hid,'advisor')[1]['accounts'])
        self.invite(hid,'advisor',['summary','financial','planning'])
        self.assertIn('personal',self.call('portfolio?id='+hid,'advisor')[1]['accounts'])

if __name__=='__main__':unittest.main()
