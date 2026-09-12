"""Bounded E1 collection, intentional crash, then new-process restart."""
import json
import subprocess
import sys
import time
from pathlib import Path
from rpc import get, put, rpc

HERE=Path(__file__).resolve().parent
RUN='run_a9c52f3b5b61'
DISPATCH='ctx_5b66ac9f894f'

def main():
    deadline=get('launch_started_at')+600
    while time.time()<deadline:
        crash=get('crash_delivery_payload') is None
        args=[sys.executable,str(HERE/'collect.py'),'--run',RUN,'--dispatch',DISPATCH]
        if crash: args.append('--crash-after-store')
        r=subprocess.run(args,capture_output=True,text=True,timeout=50)
        print(json.dumps({'collector_exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}),flush=True)
        if r.returncode==86:
            put('intentional_crash_exit',86)
            continue
        if r.returncode==10:
            continue  # empty bounded wait is not a failure or retry
        if r.returncode==0:
            return 0
        return r.returncode
    rpc('e1-deadline-stop',['orchestration','worker-stop','--dispatch',DISPATCH],mutation=True)
    put('deadline_exceeded',True)
    return 2

if __name__=='__main__':
    sys.exit(main())
