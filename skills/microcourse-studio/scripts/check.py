"""Read-only preflight. Paths are relative to the project manifest."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

STAGES = ("content", "storyboard", "prototype", "refine", "paid", "import", "deliver")
REQUIRED = {
    "content": ("outline", "script", "transcript"),
    "board": ("frames", "shot_script", "transcript", "design", "tech_audio_plan"),
    "prototype": ("browser", "timeline"),
    "final": ("browser", "video", "transcript", "qa"),
    "editor": ("draft", "sources", "import_qa"),
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def string(value):
    return isinstance(value, str) and bool(value.strip())

def positive(value):
    return type(value) is int and value > 0

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()

def fingerprint(folder, files):
    require(isinstance(files, dict) and bool(files), "empty bundle")
    hashes = {}
    for key, rel in files.items():
        require(string(rel) and not Path(rel).is_absolute(), "expected relative path")
        path = (folder / rel).resolve()
        require(folder.resolve() in path.parents and path.is_file()
                and path.stat().st_size > 0, f"missing or external: {rel}")
        with path.open("rb") as stream:
            h = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1048576), b""):
                h.update(chunk)
        hashes[key] = [rel, h.hexdigest()]
    return hashes

def timeline(m):
    cursor = 0
    paid_frames = 0
    ids = set()
    for s in m["shots"]:
        require(string(s["id"]) and s["id"] not in ids, "duplicate/empty shot ID")
        ids.add(s["id"])
        require(type(s["start"]) is int and s["start"] == cursor and positive(s["end"])
                and s["end"] > cursor, "gap/overlap/invalid frame boundary")
        require(s["route"] in ("local","external","still"), "unknown route")
        if s["route"] == "external":
            paid_frames += s["end"] - cursor
        cursor = s["end"]
    require(cursor == m["duration_frames"], "timeline duration mismatch")
    return {"external_seconds": paid_frames / m["fps"], "external_ratio": paid_frames / cursor}

def validate(m, folder, action, inspect=None):
    require(type(m["version"]) is int and m["version"] == 1, "unsupported manifest version")
    b = m["brief"]
    require(all(string(b[k]) for k in ("subject","audience","topic","theme","style","objective")), "incomplete brief")
    require(all(string(b["fonts"][k]) for k in ("title","body","caption")), "missing font role")
    require(all(positive(m[k]) for k in ("width","height","fps","duration_frames")), "invalid media spec")
    require(isinstance(m["open_issues"],list), "invalid issue list")
    require(action in STAGES, "unknown action")
    signature = digest([b, m["width"],m["height"],m["fps"],m["duration_frames"]])
    levels = {"content":0,"storyboard":1,"prototype":2,"refine":3,"paid":3,"import":4,"deliver":5}
    count = list(REQUIRED).index(inspect)+1 if inspect else levels[action]
    metrics = {}
    for stage in list(REQUIRED)[:count]:
        files = m["bundles"][stage]
        require(set(REQUIRED[stage]) <= files.keys(), f"incomplete {stage} bundle")
        if stage == "board":
            metrics = timeline(m)
        signature = digest([signature, stage, fingerprint(folder,files), m["shots"] if stage == "board" else None])
        if stage == inspect:
            return {"stage":stage, "fingerprint":signature, **metrics}
        if stage in ("content","board","final"):
            a = m["approvals"][stage]
            require(a.get("fingerprint") == signature and string(a.get("user_message")), f"missing/stale {stage} approval")
    if action in ("import","deliver"):
        require(not m["open_issues"], "resolve issues or explicitly accept and archive them")
    if action == "paid":
        q = m["batch"]
        require(q["status"] == "prepared", "pending/uncertain/submitted: inspect existing operation")
        plan = q["plan"]
        require(string(plan["batch_id"]) and string(plan["model"]) and string(plan["resolution"]) and string(plan["operation"]), "incomplete batch")
        require(isinstance(plan["items"], list) and plan["items"], "empty batch")
        ids = {s["id"] for s in m["shots"] if s["route"] == "external"}
        for item in plan["items"]:
            require(item["shot"] in ids and positive(item["seconds"]) and positive(item["count"]), "invalid batch item")
        cap = plan["quote_max"]
        a = q["approval"]
        require(string(a.get("user_message")) and a.get("fingerprint") == digest([signature,plan]), "missing/stale batch approval")
        if cap is None:
            require(a.get("accept_actual") is True and len(plan["items"]) == 1 and plan["items"][0]["count"] == 1, "unknown cost needs explicit single-item approval")
        else:
            limit = a.get("ceiling")
            require(type(cap) is int and type(limit) is int and 0 <= cap <= limit, "quote exceeds ceiling or invalid")
    return {"action":action,"check":"pass",**metrics}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest",type=Path)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--action",choices=STAGES)
    group.add_argument("--fingerprint",choices=REQUIRED)
    group.add_argument("--batch-fingerprint",action="store_true")
    args=parser.parse_args()
    try:
        m=json.loads(args.manifest.read_text(encoding="utf8"))
        if args.batch_fingerprint:
            result=validate(m,args.manifest.parent,"refine","prototype")
            result={"batch_fingerprint":digest([result["fingerprint"],m["batch"]["plan"]])}
        else:
            result=validate(m,args.manifest.parent,args.action or "content",args.fingerprint)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as error:
        print(json.dumps({"check":"blocked","reason":str(error)},ensure_ascii=False))
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
