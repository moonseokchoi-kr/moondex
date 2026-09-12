"""Actual fixture oracle, separate from the worker's completion report."""
import argparse
import json
from pathlib import Path

def verify(directory):
    source=json.loads((directory/'input.json').read_text())
    result=json.loads((directory/'output.json').read_text())
    expected={'experiment':source['experiment'],'nonce':source['nonce'],'doubled':source['value']*2}
    if result != expected:
        raise ValueError('E1_BEHAVIOR_MISMATCH')
    return {'status':'PASS','assertion':'output matches nonce and doubles fixture input'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('directory',type=Path); args=parser.parse_args()
    try:
        print(json.dumps(verify(args.directory)))
    except (OSError,ValueError,KeyError) as e:
        print(json.dumps({'status':'FAIL','reason':str(e)})); raise SystemExit(1)
