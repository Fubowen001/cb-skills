"""List, catalog and validate source skills without running their generation backends."""
import argparse,ast,json,re
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
def source_files(root):
    return sorted(p for p in Path(root).rglob('*') if p.is_file() and not any(x in ('.git','__pycache__','.venv') for x in p.parts) and p.suffix!='.pyc')
def catalog(root):
    root=Path(root);items=[]
    for folder in sorted((root/'skills').iterdir()):
        if not folder.is_dir() or folder.name.startswith('.'):continue
        p=folder/'SKILL.md'
        if not p.is_file():raise ValueError(f'{folder.name}: missing SKILL.md')
        text=p.read_text(encoding='utf-8');m=re.match(r'^---\s*\n(.*?)\n---(?:\s*\n|$)',text,re.S)
        if not m:raise ValueError(f'{folder.name}: missing YAML frontmatter')
        meta=yaml.safe_load(m.group(1))
        if not isinstance(meta,dict) or meta.get('name')!=folder.name or not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',folder.name):raise ValueError(f'{folder.name}: invalid or mismatched name')
        desc=meta.get('description')
        if not isinstance(desc,str) or not desc.strip():raise ValueError(f'{folder.name}: missing description')
        items.append({'name':folder.name,'path':p.relative_to(root).as_posix(),'description':desc})
    return {'schema':1,'skills':items}
def check(root):
    root=Path(root).resolve();expected=catalog(root);errors=[];p=root/'catalog.json'
    if not p.exists() or json.loads(p.read_text(encoding='utf8'))!=expected:errors.append('catalog.json is stale; run the catalog command')
    for p in source_files(root):
        rel=p.relative_to(root);parts=rel.parts
        if p.is_symlink():errors.append(f'{rel}: symlink is not portable');continue
        if p.name=='runtime.local.json' or (p.name.startswith('.env') and p.name!='.env.example') or p.suffix in ('.pem','.p12'):errors.append(f'{rel}: local configuration or credential file')
        if parts[0]=='skills' and any(x in ('inputs','outputs','weights','runtime','cache','work') for x in parts[2:-1]):errors.append(f'{rel}: generated or runtime directory')
        if len(parts)>1 and parts[:2]==('skills','photo-to-3d-diorama') and (p.suffix in ('.ply','.splat','.blend','.blend1','.glb','.mp4','.task') or p.name in ('job.json','batch.json')):errors.append(f'{rel}: case or runtime asset')
        if p.suffix=='.py':
            try:ast.parse(p.read_text(encoding='utf-8'),filename=str(rel))
            except (SyntaxError,UnicodeError) as e:errors.append(f'{rel}: {e}')
        if p.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
                target=target.strip().strip('<>').split('#',1)[0]
                if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://',target):continue
                if re.match(r'^[a-zA-Z]:[\\/]',target) or target.startswith('/'):
                    errors.append(f'{rel}: absolute documentation link');continue
                resolved=(p.parent/target).resolve()
                if not resolved.is_relative_to(root) or not resolved.exists():errors.append(f'{rel}: broken local link {target}')
    return errors
def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('list','catalog','check'));a=p.parse_args()
    try:
        if a.command=='catalog':(ROOT/'catalog.json').write_text(json.dumps(catalog(ROOT),ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('Updated catalog.json')
        elif a.command=='list':
            for item in catalog(ROOT)['skills']:print(item['name']+' — '+item['description'])
        else:
            errors=check(ROOT)
            if errors:print('\n'.join(errors));return 1
            print(f"PASS: {len(catalog(ROOT)['skills'])} skill(s), source and catalog checks")
    except (ValueError,OSError,yaml.YAMLError) as e:print(e);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
