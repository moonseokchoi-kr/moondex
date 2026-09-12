"""Acceptance fault injection around the production store, never a runtime option."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness_core.execution.engine import Engine
from harness_core.execution.store import Store
commit = Store.commit
def fail_after_commit(self, kind, state, detail=None):
    commit(self, kind, state, detail)
    if kind == 'delivery_stored':
        os._exit(86)
Store.commit = fail_after_commit
print(Engine(Path(sys.argv[1])).advance())
