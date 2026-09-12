"""Execution contracts. No phase ceremony and no inferred approvals."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


class ExecutionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def require(condition, message, code="INVALID_CONTRACT"):
    if not condition:
        raise ExecutionError(code, message)


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key", "STATE_INVALID")
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(), object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, "non-finite JSON"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionError("STATE_INVALID", f"unreadable JSON: {path.name}") from exc


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value), "invalid identifier")
    return value


def relative(value):
    require(isinstance(value, str) and value and "\\" not in value, "invalid relative path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and ".." not in p.parts and p.as_posix() == value, "unsafe relative path")
    return value


def within(root: Path, value: str) -> Path:
    relative(value)
    p = root / value
    require(p.resolve().is_relative_to(root.resolve()), "path escapes root", "SCOPE_VIOLATION")
    for parent in [p, *p.parents]:
        if parent == root:
            break
        require(not parent.is_symlink(), "symlink in protected path", "SCOPE_VIOLATION")
    return p


def covered(path, scopes):
    return any(s == "." or path == s or path.startswith(s.rstrip("/") + "/") for s in scopes)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(bundle):
    require(isinstance(bundle, dict) and type(bundle.get("schema_version")) is int and bundle["schema_version"] == 1, "schema_version must be 1")
    for key in ("feature", "revision"):
        identifier(bundle.get(key))
    for key in ("goal", "before", "after"):
        require(nonempty(bundle.get(key)), f"missing {key}")
    require(isinstance(bundle.get("sources"), list) and bundle["sources"], "source references required")
    require(all(isinstance(s, dict) and nonempty(s.get("source")) and nonempty(s.get("text")) for s in bundle["sources"]), "source text and location required")
    for key in ("design", "exclusions"):
        require(isinstance(bundle.get(key), list), f"{key} must be a list")
    criteria = bundle.get("criteria", [])
    require(isinstance(criteria, list) and criteria and all(isinstance(c, dict) for c in criteria), "criteria required")
    cids = set()
    for c in criteria:
        cid = identifier(c.get("id"))
        require(cid not in cids, "duplicate criterion")
        cids.add(cid)
        for key in ("requirement", "input", "action", "expected", "failure"):
            require(nonempty(c.get(key)), f"criterion missing {key}")
    policy = bundle.get("policy", {})
    require(isinstance(policy, dict), "policy must be an object")
    require(type(policy.get("concurrency")) is int and policy["concurrency"] >= 1, "positive concurrency required")
    require(policy.get("recovery_attempts") == 2, "v1 recovery policy is two repairs")
    require(policy.get("time_limit") is None and policy.get("token_limit") is None, "v1 has no time/token caps")
    inputs = bundle.get("inputs", [])
    require(inputs and all(relative(p) for p in inputs), "source input scopes required")
    require(not any(p == "." or p.startswith(".moondex") for p in inputs), "enumerate source input scopes; exclude runtime")
    gates = bundle.get("gates", [])
    require(isinstance(gates, list) and all(isinstance(g, dict) for g in gates), "gates must be objects")
    gids = set()
    for g in gates:
        gid = identifier(g.get("id"))
        require(gid not in gids, "duplicate gate")
        gids.add(gid)
        require(g.get("kind") in {"build", "unit", "integration", "e2e"}, "invalid gate kind")
        require(isinstance(g.get("argv"), list) and g["argv"] and all(nonempty(a) for a in g["argv"]), "argv required")
        require(any("{report}" in a for a in g["argv"]), "gate must emit a fresh structured {report}")
        require(g.get("format") in {"json", "junit"}, "gate report format required")
        require(type(g.get("min_tests")) is int and g["min_tests"] >= 1, "positive assertion/test count required")
        require(g.get("criteria") and set(g["criteria"]) <= cids, "gate criteria references required")
        require(isinstance(g.get("oracle"), dict) and isinstance(g["oracle"].get("argv"), list) and g["oracle"]["argv"], "negative oracle command required")
        require(all(nonempty(a) for a in g["oracle"]["argv"]) and any("{report}" in a for a in g["oracle"]["argv"]), "oracle argv/report required")
        require(nonempty(g["oracle"].get("reason")), "oracle defect explanation required")
        relative(g.get("cwd", "."))
        definitions = g.get("definitions", {})
        require(isinstance(definitions, dict), "gate definition digests must be a mapping")
        for path, proof in definitions.items():
            relative(path)
            require(isinstance(proof, str) and re.fullmatch(r"[0-9a-f]{64}", proof), "invalid gate definition digest")
        for argv in (g["argv"], g["oracle"]["argv"]):
            for argument in argv[1:]:
                if argument.endswith(".py") and not argument.startswith("-"):
                    require(argument in definitions or argument in g.get("tools", {}), "Python gate scripts must be pinned in definitions or tools")
        for path, proof in g.get("tools", {}).items():
            require(Path(path).is_absolute() and isinstance(proof, str) and re.fullmatch(r"[0-9a-f]{64}", proof), "external tool must have an absolute path and SHA256")
    coverage = bundle.get("verification", {})
    for kind in ("build", "unit", "integration", "e2e"):
        v = coverage.get(kind, {})
        require(v.get("required") is True or (v.get("required") is False and nonempty(v.get("reason"))), f"explicit {kind} applicability required")
        if v.get("required"):
            require(any(g["kind"] == kind for g in gates), f"missing required {kind} gate")
    nodes = bundle.get("nodes", [])
    require(isinstance(nodes, list) and nodes and all(isinstance(n, dict) for n in nodes), "at least one node required")
    ids = [identifier(n.get("id")) for n in nodes]
    require(len(set(ids)) == len(ids), "duplicate node")
    for n in nodes:
        for key in ("goal", "split_rationale"):
            require(nonempty(n.get(key)), f"node missing {key}")
        require(n.get("executor") in {"current", "orca"}, "invalid executor")
        for key in ("write_scope", "inputs", "outputs"):
            require(n.get(key) and all(relative(p) for p in n[key]), f"node {key} required")
        require(all(covered(p, inputs) for p in n["inputs"] + n["write_scope"] + n["outputs"]), "node paths must be in bundle source scopes")
        require(all(covered(p, n["inputs"]) for p in n["outputs"]), "node verification inputs must include its outputs")
        require(isinstance(n.get("depends_on"), list) and set(n["depends_on"]) <= set(ids) and n["id"] not in n["depends_on"], "invalid dependency")
        require(n.get("criteria") and set(n["criteria"]) <= cids, "invalid node criteria")
        require(n.get("gates") and set(n["gates"]) <= gids, "node gates required")
        mapped = set().union(*(set(g["criteria"]) for g in gates if g["id"] in n["gates"]))
        require(set(n["criteria"]) <= mapped, "unverified node criterion")
        require(isinstance(n.get("locks", []), list), "locks must be a list")
    require(bundle.get("integration_gates") and set(bundle["integration_gates"]) <= gids, "integration gates required")
    all_gates = set(bundle["integration_gates"]).union(*(set(n["gates"]) for n in nodes))
    require(all_gates == gids, "unassigned gate")
    require(cids <= set().union(*(set(g["criteria"]) for g in gates if g["id"] in bundle["integration_gates"])), "integration must cover every criterion")
    done = set()
    while len(done) < len(nodes):
        ready = {n["id"] for n in nodes if set(n["depends_on"]) <= done} - done
        require(ready, "DAG cycle")
        done |= ready
    sync = bundle.get("compound", {"enabled": False})
    if sync.get("enabled"):
        for key in ("root", "rules", "template", "index", "log", "criteria_page", "result_page"):
            require(nonempty(sync.get(key)), f"compound {key} required")
        require(type(sync.get("required")) is bool, "compound required flag missing")
        require(Path(sync["root"]).expanduser().is_absolute(), "Compound root must be explicitly absolute")
        roles = [sync[k] for k in ("rules", "template", "index", "log", "criteria_page", "result_page")]
        if sync.get("hub"):
            roles.append(sync["hub"])
        require(all(relative(p) for p in roles), "invalid Compound role path")
        require(len({p.casefold() for p in roles}) == len(roles), "Compound roles must not alias")
        require(all(sync[k].startswith("wiki/") for k in ("index", "log", "criteria_page", "result_page")), "Compound destinations must be wiki-only")
    return bundle
