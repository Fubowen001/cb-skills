"""Validate evidence-backed review records. Never infer visual approval from geometry."""
import argparse,hashlib,json
from pathlib import Path

CHECKS=('reference_fidelity','scene_coverage','identity_pose','style_consistency','assembly','multiview','interaction')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def evaluate(record,base):
    base=Path(base).resolve();errors=[];states=[]
    def locked(item,label):
        if not isinstance(item,dict) or not item.get('path') or not item.get('sha256'):
            errors.append(label+' requires path and SHA256');return
        p=(base/item['path']).resolve()
        if not p.is_file() or sha(p)!=item['sha256']:errors.append(label+' missing or changed')
    locked(record.get('candidate'),'candidate');locked(record.get('style_reference'),'style reference')
    for item in record.get('baseline_locks',[]):locked(item,'baseline')
    requested=record.get('requested_representation');actual=record.get('actual_representation')
    if requested not in ('gaussian','mesh','hybrid') or actual!=requested:errors.append('Requested representation was not delivered')
    for name in CHECKS:
        c=record.get('checks',{}).get(name,{});state=c.get('status','unreviewed');states.append(state)
        if state=='not_applicable':
            if name in ('reference_fidelity','scene_coverage','style_consistency','multiview'):errors.append(name+' cannot be skipped for a 3D scene')
            if not c.get('reason'):errors.append(name+' needs an applicability reason')
        elif state=='pass':
            if not c.get('reviewer') or not c.get('observation') or not c.get('evidence'):errors.append(name+' lacks actual review evidence')
            if c.get('candidate_sha256')!=record.get('candidate',{}).get('sha256'):errors.append(name+' review belongs to a different candidate')
            for e in c.get('evidence',[]):locked(e,name+' evidence')
        elif state not in ('fail','unreviewed'):errors.append(name+' has invalid review status')
    passed=not errors and all(s in ('pass','not_applicable') for s in states)
    policy=record.get('delivery_policy','final_only');explicit=record.get('review_requested_by_user') is True and bool(str(record.get('user_instruction','')).strip())
    if policy not in ('final_only','review_requested'):errors.append('Unknown delivery policy');passed=False
    # Invalid hashes or missing representation cannot be bypassed by a preview request.
    review_allowed=policy=='review_requested' and explicit and not errors
    return {'status':'pass' if passed else 'fail' if errors or 'fail' in states else 'needs_review','allowed_to_show':passed or review_allowed,'final_quality_approved':passed,'review_only':review_allowed and not passed,'errors':errors,'note':'This checks recorded evidence, not the truth of an unobserved visual claim.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('review');a=p.parse_args();path=Path(a.review).resolve();result=evaluate(json.loads(path.read_text(encoding='utf8')),path.parent);print(json.dumps(result,ensure_ascii=True,indent=2));raise SystemExit(0 if result['allowed_to_show'] else 2)
