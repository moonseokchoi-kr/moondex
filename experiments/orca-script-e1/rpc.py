"""Experimental Orca CLI client. Never retries an ambiguous mutation."""
from pathlib import Path
import fcntl
import json
import sqlite3
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / '.harness/state/execution/orca-script-e1'
AUDIT = ROOT / '.harness/audit/execution/orca-script-e1'

def connect():
    STATE.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STATE / 'experiment.sqlite')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS rpc (key TEXT PRIMARY KEY, argv TEXT, state TEXT, receipt TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)')
    db.commit()
    return db

def put(key, value):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, json.dumps(value)))

def get(key):
    with connect() as db:
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else None

def rpc(key, args, *, mutation=False, timeout=45):
    """Persist intent first. Successful reads are fresh; mutations cannot be blindly replayed."""
    with connect() as db:
        row = db.execute('SELECT state, receipt, argv FROM rpc WHERE key=?', (key,)).fetchone()
        argv = ['orca', *args, '--json']
        if row:
            if json.loads(row[2]) != argv:
                raise RuntimeError('Request identity reused with different arguments: '+key)
            if mutation and row[0] == 'success':
                return json.loads(row[1])
            raise RuntimeError('Existing request must be inspected, not retried: '+key)
        db.execute('INSERT INTO rpc VALUES (?,?,?,NULL)', (key,json.dumps(argv),'intent'))
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        (AUDIT / (key+'.stdout.json')).write_text(r.stdout)
        (AUDIT / (key+'.stderr.txt')).write_text(r.stderr)
        payload = json.loads(r.stdout)
        receipt = {'exit_code':r.returncode,'payload':payload,'timestamp':time.time()}
        ok = r.returncode == 0 and payload.get('ok', True)
        with connect() as db:
            db.execute('UPDATE rpc SET state=?,receipt=? WHERE key=?',
                       ('success' if ok else 'error',json.dumps(receipt),key))
        if not ok:
            raise RuntimeError('Orca request failed; inspect audit receipt: '+key)
        return receipt
    except BaseException:
        # Persisted intent/error remains and forbids accidental retries.
        raise

def lock():
    connect().close()
    f=(STATE/'writer.lock').open('a')
    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    return f

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('key')
    parser.add_argument('--mutation',action='store_true')
    parser.add_argument('args',nargs=argparse.REMAINDER)
    a=parser.parse_args()
    args=a.args[1:] if a.args and a.args[0]=='--' else a.args
    with lock():
        receipt=rpc(a.key,args,mutation=a.mutation)
    print(json.dumps(receipt['payload'],indent=2))
