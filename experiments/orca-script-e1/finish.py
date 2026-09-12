"""Verify the exact submission, apply one local effect, release, then ack."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from rpc import AUDIT, ROOT, connect, get, put, rpc, lock

RUN='run_a9c52f3b5b61'
TASK='task_84627438d791'
DISPATCH='ctx_5b66ac9f894f'

with lock():
    delivery=get('received_delivery')
    assert delivery['runId']==RUN and len(delivery['messages'])==1
    message=delivery['messages'][0]
    payload=json.loads(message['payload'])
    assert message['type']=='worker_done' and message['run_id']==RUN
    assert payload['taskId']==TASK and payload['dispatchId']==DISPATCH
    assert payload['outcome']=='succeeded'
    observed=rpc('e1-settled-worker',['orchestration','worker-show','--dispatch',DISPATCH])
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('verify_fixture.py')),str(AUDIT/'fixture')],capture_output=True,text=True)
    gate={'argv':result.args,'cwd':str(ROOT),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
          'output_sha256':hashlib.sha256((AUDIT/'fixture/output.json').read_bytes()).hexdigest()}
    (AUDIT/'fixture-gate.json').write_text(json.dumps(gate,indent=2))
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO effects VALUES (?,?)',(message['id'],'verified' if result.returncode==0 else 'failed'))
    released=rpc('e1-release-worker',['orchestration','worker-release','--dispatch',DISPATCH],mutation=True)
    put('release_receipt',released)
    print(json.dumps({'gate':gate,'release':released['payload']},indent=2))
    # Ack is a separate explicit step after inspecting actual cleanup receipt.
