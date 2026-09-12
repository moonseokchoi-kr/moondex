"""Run local negative checks without contacting Orca or launching an agent."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import subprocess
import sys
import rpc
from collect import delivery_identity

HERE=Path(__file__).resolve().parent

def check():
    outcomes=[]
    original={'runId':'r','deliveryId':'d','messages':[{'id':'m','body':'x'}],'count':1,'replayed':False,'mutation':{'requestId':'a'}}
    replay={**original,'replayed':True,'mutation':{'requestId':'b'}}
    assert delivery_identity(original)==delivery_identity(replay)
    for altered in ({**replay,'runId':'other'},{**replay,'deliveryId':'other'},{**replay,'messages':[{'id':'m','body':'changed'}]}):
        assert delivery_identity(original)!=delivery_identity(altered)
    outcomes.append('replay transport metadata may change; run/delivery/message identity cannot')
    with TemporaryDirectory(prefix='e1-offline-') as temporary:
        root=Path(temporary)
        rpc.STATE=root/'state'; rpc.AUDIT=root/'audit'
        with patch.object(rpc.subprocess,'run',side_effect=subprocess.TimeoutExpired('orca',1)) as call:
            try: rpc.rpc('unknown',['orchestration','run-create','--objective','fixture'],mutation=True)
            except subprocess.TimeoutExpired: pass
            else: raise AssertionError('Expected unknown result')
            try: rpc.rpc('unknown',['orchestration','run-create','--objective','fixture'],mutation=True)
            except RuntimeError: pass
            else: raise AssertionError('Unknown mutation was retried')
            assert call.call_count==1
        outcomes.append('ambiguous mutation is not retried')
        result=subprocess.CompletedProcess([],0,json.dumps({'ok':True,'result':{}}),'')
        with patch.object(rpc.subprocess,'run',return_value=result) as call:
            rpc.rpc('once',['orchestration','run-create','--objective','fixture'],mutation=True)
            rpc.rpc('once',['orchestration','run-create','--objective','fixture'],mutation=True)
            try: rpc.rpc('once',['orchestration','run-create','--objective','different'],mutation=True)
            except RuntimeError: pass
            else: raise AssertionError('Changed request reused identity')
            assert call.call_count==1
        outcomes.append('successful request replay caches receipt; changed arguments rejected')
        code='''import os,sys
from pathlib import Path
import rpc,collect
rpc.STATE=Path(sys.argv[1])/'state'
rpc.AUDIT=Path(sys.argv[1])/'audit'
collect.initialize()
collect.store_delivery([{'id':'m1','type':'worker_done'}])
os._exit(int(sys.argv[2]))
'''
        for exit_code in (86,0):
            p=subprocess.run([sys.executable,'-c',code,str(root),str(exit_code)],cwd=HERE)
            assert p.returncode==exit_code
        with rpc.connect() as db:
            assert db.execute('SELECT count(*) FROM inbox').fetchone()[0]==1
        outcomes.append('real process exit and replay preserve exactly one inbox row')
        fixture=root/'fixture'; fixture.mkdir()
        (fixture/'input.json').write_text(json.dumps({'experiment':'e1','nonce':'n','value':21}))
        for value,exit_code in [(None,1),({'experiment':'e1','nonce':'n','doubled':41},1),({'experiment':'e1','nonce':'old','doubled':42},1),({'experiment':'e1','nonce':'n','doubled':42},0)]:
            if value is not None: (fixture/'output.json').write_text(json.dumps(value))
            p=subprocess.run([sys.executable,str(HERE/'verify_fixture.py'),str(fixture)],capture_output=True,text=True)
            assert p.returncode==exit_code
        outcomes.append('oracle rejects missing/wrong/stale output and accepts valid output')
    return {'status':'PASS','checks':outcomes,'live_orca':False}

if __name__=='__main__':
    print(json.dumps(check(),indent=2))
