import unittest,tempfile,sys,json,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from manage_skills import catalog,check
class Repository(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('PHOTO3D_TEST_TMP'));self.root=Path(self.tmp.name);p=self.root/'skills/example';p.mkdir(parents=True);(p/'SKILL.md').write_text('---\nname: example\ndescription: Example skill.\n---\nExample\n',encoding='utf8');self.refresh()
 def tearDown(self):self.tmp.cleanup()
 def refresh(self):(self.root/'catalog.json').write_text(json.dumps(catalog(self.root)),encoding='utf8')
 def test_valid_repository(self):self.assertEqual(check(self.root),[])
 def test_catalog_must_be_updated(self):
  (self.root/'catalog.json').write_text('{}');self.assertTrue(check(self.root))
 def test_skill_name_matches_directory(self):
  p=self.root/'skills/example/SKILL.md';p.write_text(p.read_text().replace('name: example','name: other'))
  with self.assertRaises(ValueError):catalog(self.root)
 def test_private_configuration_is_rejected(self):
  (self.root/'skills/example/runtime.local.json').write_text('{}');self.assertTrue(check(self.root))
 def test_broken_reference_is_rejected(self):
  p=self.root/'skills/example/SKILL.md';p.write_text(p.read_text()+'[Missing](references/missing.md)\n');self.assertTrue(check(self.root))
 def test_future_skill_assets_are_allowed(self):
  p=self.root/'skills/example/assets';p.mkdir();(p/'illustration.png').write_bytes(b'fixture');self.assertEqual(check(self.root),[])
if __name__=='__main__':unittest.main()
