import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SKILL/'scripts'))
from check import REQUIRED, digest, validate

class FlowTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.m=json.loads((SKILL/'assets/project.example.json').read_text())
        self.m['shots']=[{'id':'A','start':0,'end':120,'route':'external'},
                         {'id':'B','start':120,'end':10800,'route':'local'}]
        for stage,roles in REQUIRED.items():
            files={}
            for key in roles:
                name=stage+'-'+key
                (self.root/name).write_text(name)
                files[key]=name
            self.m['bundles'][stage]=files
            if stage in ('content','board','final'):
                fp=validate(self.m,self.root,'content',stage)['fingerprint']
                self.m['approvals'][stage]={'fingerprint':fp,'user_message':'TEST fixture approval'}
        self.plan={'batch_id':'sample','operation':'sample','model':'fixture','resolution':'low',
                   'items':[{'shot':'A','seconds':2,'count':1}],'quote_max':6}
        self.sign()

    def sign(self):
        fp=validate(self.m,self.root,'refine','prototype')['fingerprint']
        self.m['batch']={'plan':self.plan,'status':'prepared','approval':{
            'fingerprint':digest([fp,self.plan]),'user_message':'TEST','ceiling':6}}

    def call(self,action):return validate(self.m,self.root,action)
    def blocked(self,action):
        with self.assertRaises((ValueError,KeyError)):self.call(action)

    def test_complete(self):
        for stage in ('content','storyboard','prototype','refine','paid','import','deliver'):
            self.assertEqual(self.call(stage)['check'],'pass')
    def test_ratio(self): self.assertEqual(self.call('refine')['external_seconds'],2)
    def test_no_approval(self):
        self.m['approvals'].pop('content');self.blocked('storyboard')
    def test_missing_font(self):
        self.m['brief']['fonts']['title']=' ';self.blocked('content')
    def test_bad_duration(self):
        self.m['duration_frames']=False;self.blocked('content')
    def test_replaced_image(self):
        (self.root/'board-frames').write_text('new image');self.blocked('prototype')
    def test_missing_sources(self):
        (self.root/'editor-sources').unlink();self.blocked('deliver')
    def test_external_path(self):
        self.m['bundles']['content']['outline']='../secret';self.blocked('storyboard')
    def test_gap(self):
        self.m['shots'][1]['start']+=1;self.blocked('prototype')
    def test_duplicate(self):
        self.m['shots'][1]['id']='A';self.blocked('prototype')
    def test_incomplete_timeline(self):
        self.m['shots'][1]['end']-=1;self.blocked('prototype')
    def test_stale_batch(self):
        self.plan['resolution']='HD';self.blocked('paid')
    def test_over_budget(self):
        self.m['batch']['approval']['ceiling']=5;self.blocked('paid')
    def test_unknown_price(self):
        self.plan['quote_max']=None;self.sign();self.blocked('paid')
        self.m['batch']['approval']['accept_actual']=True;self.call('paid')
    def test_unknown_multiple(self):
        self.plan['quote_max']=None;self.plan['items'][0]['count']=2;self.sign()
        self.m['batch']['approval']['accept_actual']=True;self.blocked('paid')
    def test_unknown_submission(self):
        self.m['batch']['status']='unknown';self.blocked('paid')
    def test_unresolved_final(self):
        self.m['open_issues']=['lip sync'];self.blocked('import')
    def test_revised_final(self):
        (self.root/'final-video').write_text('v2');self.blocked('import')
    def test_import_requires_approval(self):
        self.m['approvals'].pop('final');self.blocked('import')

if __name__=='__main__':unittest.main()
