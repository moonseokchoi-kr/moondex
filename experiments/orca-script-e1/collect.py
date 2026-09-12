"""Experimental one-Dispatch collector; crash/restart does not duplicate local effects.

No worker launch here. Receipt format must match the installed public contract;
unknown payload shapes are preserved and stop processing before acknowledgement.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from rpc import AUDIT, ROOT, connect, get, lock, put, rpc


def initialize():
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS inbox (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS effects (id TEXT PRIMARY KEY, kind TEXT NOT NULL)')


def store_delivery(messages):
    with connect() as db:
        for message in messages:
            mid=message.get('id')
            if not isinstance(mid,str) or not mid:
                raise ValueError('Message ID unavailable; no acknowledgement')
            body=json.dumps(message,sort_keys=True)
            prior=db.execute('SELECT body FROM inbox WHERE id=?',(mid,)).fetchone()
            if prior and prior[0] != body:
                raise ValueError('Replayed message changed; no acknowledgement')
            db.execute('INSERT OR IGNORE INTO inbox VALUES (?,?)',(mid,body))


def delivery_identity(payload):
    return {k:payload[k] for k in ("runId","deliveryId","messages","count")}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--dispatch',required=True)
    parser.add_argument('--crash-after-store',action='store_true')
    args=parser.parse_args()
    with lock():
        initialize()
        attempt=uuid.uuid4().hex[:12]
        receipt=rpc('collect-'+attempt,['orchestration','check','--run',args.run,'--wait',
                    '--types','worker_done,escalation,question','--timeout-ms','30000'],timeout=40)
        payload=receipt['payload']['result']
        messages=payload.get('messages')
        if not isinstance(messages,list):
            raise ValueError('Unknown Delivery shape; inspect raw receipt')
        if not messages:
            print(json.dumps({'status':'WAITING','failed':False})); return 10
        store_delivery(messages)
        if args.crash_after_store:
            put('crash_delivery_payload',payload)
            os._exit(86)  # intentional crash after SQLite commit, before ack/cleanup
        previous=get('crash_delivery_payload')
        if previous is not None and delivery_identity(previous) != delivery_identity(payload):
            raise ValueError('Delivery changed across restart; inspect before proceeding')
        # Inspect the actual live schema before allowing any release or ack.
        put('received_delivery',payload)
        print(json.dumps({'status':'DELIVERY_DURABLE','messages':len(messages),
                          'same_delivery_after_restart':previous is not None and delivery_identity(previous) == delivery_identity(payload)}))
        return 0

if __name__=='__main__':
    sys.exit(main())
