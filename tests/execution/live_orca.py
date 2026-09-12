"""Explicit live acceptance probe. Never discovered by the offline pytest suite.

Run prepare once, then step until ACTION integration_review, submit that observed
review, and step to COMPLETED. Uses the production engine and its actual adapter.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness_core.execution.engine import Engine


def make_bundle():
    b = {"schema_version": 1, "feature": "live-orca-abc", "revision": "r1",
         "goal": "Production script executes independent A/B and dependent C, verifies their real outputs and cleans up owned workers",
         "before": "three outputs absent", "after": "A=42 B=22 C=84 with C starting after verified A",
         "sources": [{"source": "approved implementation plan I4/I6", "text": "Actual Orca A/B and A-dependent C; concurrency 2; no time/token cap, automatic repair 2."}],
         "design": ["Use production scheduler and existing current worktree; modify fixture files only"],
         "exclusions": ["No other worktrees, no product edits by fixture workers, no additional workers"],
         "inputs": ["src"], "criteria": [], "nodes": [], "gates": [], "integration_gates": [],
         "policy": {"concurrency": 2, "recovery_attempts": 2, "time_limit": None, "token_limit": None},
         "verification": {k: {"required": k == "e2e", "reason": "Production Orca arithmetic fixture"} for k in ("build", "unit", "integration", "e2e")},
         "compound": {"enabled": False}}
    for name, expected, goal in [("A",42,"Write JSON number 42 (21 doubled) to src/a.json"),
                                  ("B",22,"Write JSON number 22 (11 doubled) to src/b.json"),
                                  ("C",84,"Read src/a.json and write twice that number as JSON number to src/c.json")]:
        path = f"src/{name.lower()}.json"
        cid = "C" + name
        b["criteria"].append({"id": cid, "requirement": "A06", "input": "21/11 or verified A", "action": goal,
                              "expected": str(expected), "failure": f"{expected+1} must be rejected"})
        code = f"""import json,sys
from pathlib import Path
v = json.loads(Path({path!r}).read_text())
if sys.argv[2] == 'defect': v += 1
ok = type(v) is int and v == {expected}
Path(sys.argv[1]).write_text(json.dumps({{'tests':1,'failures':int(not ok),'criteria':{{{cid!r}:ok}}}}))
sys.exit(0 if ok else 1)
"""
        b["gates"].append({"id": "gate"+name, "kind": "e2e", "argv": [sys.executable,"-c",code,"{report}","actual"],
                           "format":"json","min_tests":1,"criteria":[cid],
                           "oracle":{"argv":[sys.executable,"-c",code,"{report}","defect"],"reason":"reject off-by-one output"}})
        b["nodes"].append({"id": name,"goal":goal,"executor":"orca","inputs":[path]+(["src/a.json"] if name=="C" else []),
                           "write_scope":[path],"outputs":[path],"depends_on":["A"] if name=="C" else [],
                           "criteria":[cid],"gates":["gate"+name],"locks":[],
                           "split_rationale":"Independent fixture outputs; C reads A only after production verification"})
        b["integration_gates"].append("gate"+name)
    return b


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["prepare","step","status"])
    p.add_argument("--root",type=Path,required=True)
    args=p.parse_args()
    e=Engine(args.root)
    if args.command=="prepare":
        ready=e.prepare(make_bundle())
        result=e.approve(ready["digest"],"Implement the plan.","current conversation: approved actual Orca A/B/C acceptance")
    elif args.command=="step": result=e.advance()
    else:
        s=e.store.status();result={"status":s["status"],"nodes":{k:v["status"] for k,v in s["nodes"].items()},"questions":[q for q in s["questions"].values() if q["status"]=="OPEN"]}
    print(json.dumps(result,ensure_ascii=False))
