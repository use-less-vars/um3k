#!/usr/bin/env python3.12
"""Throwaway AST mapper for the poc_app monolith. Writes artifacts/structure/*."""
import ast, json, os, re, sys, difflib
from collections import defaultdict, Counter

sys.setrecursionlimit(20000)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "artifacts/structure")
os.makedirs(OUT, exist_ok=True)
MODS = ["server/poc_app.py", "server/um3k_panels.py", "server/um3k_context.py"]

SRC, TREE, LINES = {}, {}, {}
for m in MODS:
    p = os.path.join(ROOT, m)
    s = open(p, encoding="utf-8", errors="replace").read()
    SRC[m] = s
    LINES[m] = s.splitlines()
    TREE[m] = ast.parse(s, filename=p)

defs, classes, refs = [], [], []
writes, reads = [], []
calls_list = []
bases = Counter()
write_ids = {}
line_events = defaultdict(Counter)

def dname(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        b = dname(node.value)
        return f"{b}.{node.attr}" if b else node.attr
    if isinstance(node, ast.Call):
        return dname(node.func)
    if isinstance(node, ast.Subscript):
        return dname(node.value)
    return ""

def deco_str(d):
    try:
        return ast.unparse(d)
    except Exception:
        return "?"

def argcount(a):
    n = len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs)
    if a.args and a.args[0].arg in ("self", "cls"):
        n -= 1
    return n + (1 if a.vararg else 0) + (1 if a.kwarg else 0)

def collect_write_ids(tree):
    ids = set()
    for n in ast.walk(tree):
        tg = []
        if isinstance(n, ast.Assign):
            tg = n.targets
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor, ast.NamedExpr)):
            tg = [n.target]
        for t in tg:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Attribute) and dname(sub).split(".")[0] == "state":
                    ids.add(id(sub))
    return ids

def record_ref(node, mod, owner):
    if isinstance(node, ast.Name):
        refs.append((node.id, mod, owner, node.lineno, "name"))
    elif isinstance(node, ast.Attribute):
        refs.append((node.attr, mod, owner, node.lineno, "attr"))

def ctr_deco(r):
    return ";".join(d for d in r["decorators"] if re.search(r"(change|on_event|trigger|\.set\b)", d))

def vis(node, mod, qual, scope, frec):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if scope == "module":
            q = node.name
        elif scope == "class":
            q = f"{qual}.{node.name}"
        else:
            q = f"{qual}.<locals>.{node.name}"
        decos = [deco_str(d) for d in node.decorator_list]
        kind = "function"
        if scope == "class":
            if any(d.split("(")[0].endswith("classmethod") for d in decos):
                kind = "classmethod"
            elif any(d.split("(")[0].endswith("staticmethod") for d in decos):
                kind = "staticmethod"
            else:
                kind = "method"
        doc = ast.get_docstring(node) or ""
        rec = dict(module=mod, qual=q, kind=kind, start=node.lineno, end=node.end_lineno,
                   n_args=argcount(node.args), decorators=decos,
                   is_async=isinstance(node, ast.AsyncFunctionDef),
                   doc=doc.strip().splitlines()[0].strip() if doc.strip() else "",
                   has_deco=bool(decos), depth=q.count("."), ui=0, state=0, calls=Counter())
        defs.append(rec)
        line_events[(mod, node.lineno)]["def"] += 1
        for d in node.decorator_list:
            vis(d, mod, qual, scope, frec)
        for a in node.args.defaults + [x for x in node.args.kw_defaults if x]:
            vis(a, mod, qual, scope, frec)
        for st in node.body:
            vis(st, mod, q, "function", rec)
        return
    if isinstance(node, ast.ClassDef):
        q = node.name if scope == "module" else (f"{qual}.{node.name}" if scope == "class" else f"{qual}.<locals>.{node.name}")
        doc = ast.get_docstring(node) or ""
        classes.append(dict(module=mod, name=q, start=node.lineno, end=node.end_lineno,
                            bases=[dname(b) for b in node.bases],
                            decos=[deco_str(d) for d in node.decorator_list],
                            doc=doc.strip().splitlines()[0].strip() if doc.strip() else "",
                            methods=[n.name for n in node.body
                                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]))
        for b in node.bases:
            vis(b, mod, qual, scope, frec)
        for d in node.decorator_list:
            vis(d, mod, qual, scope, frec)
        for st in node.body:
            vis(st, mod, q, "class", frec)
        return
    owner = frec["qual"] if frec else None
    if isinstance(node, (ast.Name, ast.Attribute)):
        record_ref(node, mod, owner)
        dn = dname(node)
        parts = dn.split(".")
        if len(parts) > 1 and parts[0] == "state":
            key = parts[1]
            if id(node) in write_ids.get(mod, ()):
                writes.append((mod, key, owner, node.lineno))
            elif isinstance(getattr(node, "ctx", ast.Load()), ast.Load):
                reads.append((mod, key, owner, node.lineno))
        if parts[0] == "ui":
            line_events[(mod, node.lineno)]["ui"] += 1
        if parts[0] == "state":
            line_events[(mod, node.lineno)]["state"] += 1
        if frec is not None:
            if parts[0] == "ui":
                frec["ui"] += 1
            if parts[0] == "state":
                frec["state"] += 1
            nm = node.id if isinstance(node, ast.Name) else node.attr
            if nm not in ("state", "ui", "self", "cls"):
                frec["calls"][nm] += 1
    if isinstance(node, ast.Call):
        dn2 = dname(node.func)
        base2 = dn2.split(".")[0] if dn2 else "?"
        calls_list.append((dn2.split(".")[-1], owner, node.lineno, dn2))
        bases[base2] += 1
        if frec is not None:
            frec.setdefault("bases", Counter())[base2] += 1
    for ch in ast.iter_child_nodes(node):
        vis(ch, mod, qual, scope, frec)

for m in MODS:
    write_ids[m] = collect_write_ids(TREE[m])
    for st in TREE[m].body:
        vis(st, m, None, "module", None)

for r in defs:
    r["n_lines"] = r["end"] - r["start"] + 1

UI_BASES = {"html_div", "html_widgets", "widgets", "widgets_module", "ui_module",
            "SinglePageLayout", "layout", "ctrl", "ctx", "VRow", "VCol", "placeholder",
            "clim_cls", "alert_cls", "run_field", "img_cls", "pre_cls", "btn_cls", "nt"}
RENDER_BASES = {"plotter", "pv", "fig", "ax", "mesh", "geometry", "geom", "plt"}

def klass(r):
    b = set((r.get("bases") or {}).keys())
    if b & UI_BASES or r["state"]:
        return "ui"
    if b & RENDER_BASES:
        return "render"
    return "engine"

for r in defs:
    r["klass"] = klass(r)

# ---------- A) functions.tsv ----------
def flagstr(r):
    f = []
    if r["klass"] == "ui":
        f.append("touches_ui")
    elif r["klass"] == "render":
        f.append("touches_render")
    if r["state"]:
        f.append("touches_state")
    if ctr_deco(r):
        f.append("is_controller")
    if r["is_async"]:
        f.append("is_async")
    return "|".join(f)

def clean(s):
    return str(s).replace("\t", " ").replace("\n", " ").replace("\r", " ")

hdr = ["module", "qualname", "kind", "start_line", "end_line", "n_lines", "n_args",
       "decorators", "flags", "controller_decorator", "docstring_first_line"]
rows = []
for r in defs:
    rows.append([r["module"], r["qual"], r["kind"], r["start"], r["end"], r["n_lines"],
                 r["n_args"], " ".join(r["decorators"]), flagstr(r), ctr_deco(r), r["doc"]])
with open(os.path.join(OUT, "functions.tsv"), "w", encoding="utf-8") as fh:
    fh.write("\t".join(hdr) + "\n")
    for row in rows:
        fh.write("\t".join(clean(c) for c in row) + "\n")
with open(os.path.join(OUT, "functions_by_size.tsv"), "w", encoding="utf-8") as fh:
    fh.write("\t".join(hdr) + "\n")
    for row in sorted(rows, key=lambda x: -x[5]):
        fh.write("\t".join(clean(c) for c in row) + "\n")

# ---------- B) classes.tsv ----------
def role_guess(c):
    if c["doc"]:
        return c["doc"]
    ms = [m for m in c["methods"] if not m.startswith("__")]
    b = ",".join(x for x in c["bases"] if x != "object") or "plain"
    return f"{b} with {len(ms)} methods: " + ", ".join(ms[:4])

with open(os.path.join(OUT, "classes.tsv"), "w", encoding="utf-8") as fh:
    fh.write("\t".join(["module", "name", "start_line", "end_line", "n_lines", "n_methods",
                        "bases", "decorators", "role_guess"]) + "\n")
    for c in classes:
        fh.write("\t".join(clean(x) for x in [
            c["module"], c["name"], c["start"], c["end"], c["end"] - c["start"] + 1,
            len(c["methods"]), ",".join(c["bases"]), " ".join(c["decos"]), role_guess(c)]) + "\n")

# ---------- C) state_keys.tsv ----------
W, R = defaultdict(set), defaultdict(set)
for mod, key, owner, ln in writes:
    W[(mod, key)].add((ln, owner or "<module>"))
for mod, key, owner, ln in reads:
    R[(mod, key)].add((ln, owner or "<module>"))
keys = sorted(set(W) | set(R), key=lambda k: -(len(R.get(k, ())) + len(W.get(k, ()))))
multi = 0
with open(os.path.join(OUT, "state_keys.tsv"), "w", encoding="utf-8") as fh:
    fh.write("\t".join(["module", "key", "n_writes", "n_reads", "n_writer_funcs", "n_reader_funcs",
                        "first_write_sites", "first_read_sites"]) + "\n")
    for mod, key in keys:
        w = sorted(W.get((mod, key), ()))
        r = sorted(R.get((mod, key), ()))
        wf = {o for _, o in w}
        rf = {o for _, o in r}
        if len(wf) > 1:
            multi += 1
        fh.write("\t".join(clean(x) for x in [
            mod, key, len(w), len(r), len(wf), len(rf),
            "; ".join(f"{ln}:{o}" for ln, o in w[:3]),
            "; ".join(f"{ln}:{o}" for ln, o in r[:3])]) + "\n")

# ---------- duplicated string literals ----------
strs = defaultdict(list)
for m in MODS:
    for n in ast.walk(TREE[m]):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) >= 150:
            strs[re.sub(r"\s+", " ", n.value.strip())].append((m, n.lineno, len(n.value)))
dupstr = sorted(((k, v) for k, v in strs.items() if len(v) > 1), key=lambda kv: -kv[1][0][2])

# ---------- duplication on bodies ----------
def body_lines(r):
    ls = LINES[r["module"]][r["start"] - 1:r["end"]]
    i = 0
    while i < len(ls) and not ls[i].rstrip().endswith(":"):
        i += 1
    norm = []
    for ln in ls[i + 1:]:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        norm.append(s)
    return norm

BODY = {f"{r['qual']}@{r['start']}": body_lines(r) for r in defs if r["module"] == "server/poc_app.py"}
exact = defaultdict(list)
for k, v in BODY.items():
    if len(v) >= 8:
        exact[tuple(v)].append(k)
exact_dups = sorted(((v, k) for k, v in exact.items() if len(v) > 1), key=lambda kv: -len(kv[1]))

cands = [(k, v) for k, v in BODY.items() if len(v) >= 25]
sets = {k: set(v) for k, v in cands}
pairs = []
for i in range(len(cands)):
    for j in range(i + 1, len(cands)):
        a, b = cands[i][0], cands[j][0]
        sa, sb = sets[a], sets[b]
        jac = len(sa & sb) / max(1, len(sa | sb))
        if jac >= 0.45:
            pairs.append((jac, a, b))
pairs.sort(reverse=True)
near = []
for jac, a, b in pairs[:500]:
    r = difflib.SequenceMatcher(None, BODY[a], BODY[b]).ratio()
    if r >= 0.72:
        near.append((round(r, 3), a, b, len(BODY[a]), len(BODY[b])))
near.sort(reverse=True)

sh = defaultdict(set)
for k, v in BODY.items():
    for i in range(len(v) - 3):
        sh[tuple(v[i:i + 4])].add(k.split("@")[0])
reps = sorted(((len(f), blk) for blk, f in sh.items() if len(f) >= 3), reverse=True)

# ---------- dead code ----------
findex = defaultdict(list)
for r in defs:
    findex[r["qual"].split(".")[-1]].append(r)
refcnt = Counter()
for nm, mod, owner, ln, kind in refs:
    for r in findex.get(nm, ()):
        if owner != r["qual"]:
            refcnt[r["qual"]] += 1
# name-or-call only (no bare attribute credit)
refcnt_nc = Counter()
for nm, mod, owner, ln, kind in refs:
    if kind == "name":
        for r in findex.get(nm, ()):
            if owner != r["qual"]:
                refcnt_nc[r["qual"]] += 1
for last, owner, ln, dn2 in calls_list:
    for r in findex.get(last, ()):
        if owner != r["qual"]:
            refcnt_nc[r["qual"]] += 1

test_refs = set()
tests_dir = os.path.join(ROOT, "tests")
if os.path.isdir(tests_dir):
    for fn in sorted(os.listdir(tests_dir)):
        if not fn.endswith(".py"):
            continue
        try:
            t = ast.parse(open(os.path.join(tests_dir, fn), encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for n in ast.walk(t):
            if isinstance(n, ast.Name):
                test_refs.add(n.id)
            elif isinstance(n, ast.Attribute):
                test_refs.add(n.attr)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                test_refs.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", n.value))

def sideeffect(r):
    return any(not re.match(r"^(staticmethod|classmethod|property|functools\.|abc\.)", d) for d in r["decorators"])

roots = {r["qual"] for r in defs
         if sideeffect(r) or r["qual"].split(".")[-1] in test_refs or r["qual"] == "main"}
for nm, mod, owner, ln, kind in refs:
    if owner is None:
        for r in findex.get(nm, ()):
            roots.add(r["qual"])
seen, stack = set(roots), list(roots)
qualmap = {r["qual"]: r for r in defs}
while stack:
    q = stack.pop()
    r = qualmap.get(q)
    if not r:
        continue
    for nm in r["calls"]:
        for t in findex.get(nm, ()):
            if t["qual"] not in seen:
                seen.add(t["qual"])
                stack.append(t["qual"])
unreach = [r for r in defs if r["qual"] not in seen]
unref = [r for r in defs if not refcnt[r["qual"]] and r["qual"].split(".")[-1] not in test_refs
         and not sideeffect(r) and r["qual"] != "main"]
testonly = [r for r in defs if not refcnt[r["qual"]] and r["qual"].split(".")[-1] in test_refs]

# ---------- engine vs UI ----------
mod_funcs = [r for r in defs if r["module"] == "server/poc_app.py" and r["kind"] == "function" and r["depth"] == 0]
ui_f = [r for r in mod_funcs if r["klass"] == "ui"]
ren_f = [r for r in mod_funcs if r["klass"] == "render"]
eng_f = [r for r in mod_funcs if r["klass"] == "engine"]
all_ui = [r for r in defs if r["klass"] == "ui"]
all_ren = [r for r in defs if r["klass"] == "render"]
all_eng = [r for r in defs if r["klass"] == "engine"]

# ---------- sections: banners / buckets ----------
banners = []
for i, ln in enumerate(LINES["server/poc_app.py"], 1):
    s = ln.rstrip()
    if not s.startswith("#"):
        continue
    b = s.lstrip("#").strip()
    if len(b) < 4 or len(b) > 92:
        continue
    if re.search(r"(===|---|──|___|\*\*\*|###)", s) or re.match(r"^[=\-─ *#]{6,}$", s):
        banners.append((i, s[:100]))
    elif b.isupper() and len(b) >= 6:
        banners.append((i, s[:100]))

buck = []
NL = len(LINES["server/poc_app.py"])
for b0 in range(0, NL, 250):
    c = Counter()
    for l in range(b0 + 1, min(b0 + 251, NL + 1)):
        e = line_events.get(("server/poc_app.py", l))
        if e:
            c.update(e)
    buck.append((b0 + 1, c["ui"], c["state"], c["def"]))

imports, consts = [], []
for n in TREE["server/poc_app.py"].body:
    if isinstance(n, ast.Import):
        imports.append((n.lineno, "import", ", ".join(a.name + (" as " + a.asname if a.asname else "") for a in n.names)))
    elif isinstance(n, ast.ImportFrom):
        imports.append((n.lineno, "from", f"{'.' * (n.level or 0)}{n.module or ''} import " + ", ".join(a.name for a in n.names)))
    elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
        try:
            v = ast.unparse(n.value)
        except Exception:
            v = "?"
        consts.append((n.lineno, n.targets[0].id, v[:110]))

main_guard = [(n.lineno, n.end_lineno, ast.unparse(n.test)[:120]) for n in TREE["server/poc_app.py"].body
              if isinstance(n, ast.If) and "main" in ast.unparse(n.test)]

# ---------- digest ----------
D = []
P = D.append
P("files: " + ", ".join(f"{m}={len(LINES[m])} lines" for m in MODS))
P(f"defs={len(defs)} classes={len(classes)} state_keys={len(keys)} multi_writer_keys={multi}")
P(f"module funcs={len(mod_funcs)} ui-ish={len(ui_f)} ({sum(r['n_lines'] for r in ui_f)} lines) "
  f"engine-ish={len(eng_f)} ({sum(r['n_lines'] for r in eng_f)} lines)")
P(f"unref={len(unref)} testonly={len(testonly)} unreachable_from_roots={len(unreach)}")
P("\n== module docstring ==")
P((ast.get_docstring(TREE['server/poc_app.py']) or '')[:900])
P("\n== imports (poc_app) ==")
for ln, kind, s in imports:
    P(f"{ln}\t{kind}\t{s}")
P("\n== module-level assignments (poc_app, targets=Name) ==")
for ln, name, v in consts:
    P(f"{ln}\t{name} = {v}")
P("\n== main guard ==")
for t in main_guard:
    P(str(t))
P("\n== banner-ish comments (poc_app) ==")
for ln, s in banners:
    P(f"{ln}\t{s}")
P("\n== 250-line buckets: start n_ui n_render n_engine lines_ui lines_render lines_engine ==")
bk = defaultdict(lambda: Counter())
for r in defs:
    if r["module"] != "server/poc_app.py":
        continue
    b0 = ((r["start"] - 1) // 250) * 250 + 1
    bk[b0][r["klass"] + "_n"] += 1
    bk[b0][r["klass"] + "_l"] += r["n_lines"]
for b0 in sorted(bk):
    c = bk[b0]
    P(f"{b0}\t{c['ui_n']}\t{c['render_n']}\t{c['engine_n']}\t{c['ui_l']}\t{c['render_l']}\t{c['engine_l']}")
P("\n== classes ==")
for c in classes:
    P(f"{c['module']}\t{c['name']}\t{c['start']}-{c['end']}\tmethods={len(c['methods'])}\tbases={c['bases']}\tdecos={c['decos']}")
P("\n== top 25 by size ==")
for r in sorted(defs, key=lambda r: -r["n_lines"])[:25]:
    P(f"{r['n_lines']:5d}\t{r['module']}\t{r['qual']}\t{r['start']}-{r['end']}\targs={r['n_args']}\tui={r['ui']}\tstate={r['state']}\t{r['doc'][:70]}")
P("\n== exact duplicate bodies (>=8 norm lines) ==")
for grp, k in exact_dups[:15]:
    P(f"n={len(k)} lines={len(grp)} :: " + " | ".join(k))
P("\n== near-duplicate pairs (ratio>=0.72) ==")
for r in near[:25]:
    P(str(r))
P("\n== repeated 4-line blocks in >=3 functions ==")
for cnt, blk in reps[:20]:
    P(f"in {cnt} funcs :: " + " / ".join(blk))
P("\n== duplicated long string literals ==")
for k, v in dupstr[:12]:
    P(f"x{len(v)} len={v[0][2]} at {[(m.split('/')[-1], ln) for m, ln, _ in v]} :: {k[:110]}")
P("\n== unreferenced funcs ==")
for r in sorted(unref, key=lambda r: -r["n_lines"])[:60]:
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}\tdecos={r['decorators']}")
P("\n== test-only referenced ==")
for r in testonly[:40]:
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}")
P("\n== unreachable from roots (top 40 by size) ==")
for r in sorted(unreach, key=lambda r: -r["n_lines"])[:40]:
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}")
P("\n== biggest engine-only module funcs ==")
for r in sorted(eng_f, key=lambda r: -r["n_lines"])[:30]:
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}-{r['end']}\targs={r['n_args']}\t{r['doc'][:60]}")
strict = Counter()
for last, owner, ln, dn2 in calls_list:
    for r in findex.get(last, ()):
        if owner != r["qual"]:
            strict[r["qual"]] += 1
unref_strict = [r for r in defs if not strict[r["qual"]] and not sideeffect(r)
                and r["qual"].split(".")[-1] not in test_refs and r["qual"] != "main"]
P(f"\n== call bases (top 70) == ")
for b, c in bases.most_common(70):
    P(f"{c}\t{b}")
P(f"\n== unref by CALL graph only: {len(unref_strict)} ==")
for r in sorted(unref_strict, key=lambda r: -r["n_lines"]):
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}\tbases={dict((r.get('bases') or {}))}")
P("\n== classification totals (all defs, incl nested) ==")
for nm2, grp in (("ui", all_ui), ("render", all_ren), ("engine", all_eng)):
    P(f"{nm2}\t{len(grp)} defs\t{sum(r['n_lines'] for r in grp)} lines")
P("== module-level only ==")
for nm2, grp in (("ui", ui_f), ("render", ren_f), ("engine", eng_f)):
    P(f"{nm2}\t{len(grp)} defs\t{sum(r['n_lines'] for r in grp)} lines")
P("\n== engine-class funcs touching state/ui (crossing) ==")
for r in defs:
    if r["klass"] == "engine" and (r["state"] or r["ui"]):
        P(f"{r['n_lines']:5d}\t{r['qual']}\tstate={r['state']}")
P("\n== ALL module-level defs in order (line, qual, n_lines, klass, doc) ==")
for r in sorted(mod_funcs, key=lambda r: r["start"]):
    P(f"{r['start']:6d}-{r['end']:<6d}{r['n_lines']:5d}\t{r['klass']}\t{r['qual']}\t{r['doc'][:80]}")
P("\n== nested defs (non-module-level) in order ==")
for r in sorted([r for r in defs if r["depth"] > 0 and r["module"] == "server/poc_app.py"], key=lambda r: r["start"]):
    P(f"{r['start']:6d}-{r['end']:<6d}{r['n_lines']:5d}\t{r['klass']}\t{r['qual']}\t{r['doc'][:70]}")
P("\n== unref by name-or-call graph ==")
unref2 = [r for r in defs if not refcnt_nc[r["qual"]] and not sideeffect(r)
          and r["qual"].split(".")[-1] not in test_refs and r["qual"] != "main"]
P(f"count={len(unref2)}")
for r in sorted(unref2, key=lambda r: -r["n_lines"]):
    P(f"{r['n_lines']:5d}\t{r['qual']}\t{r['start']}\t{r['klass']}")
P("\n== controller-decorated funcs ==")
for r in defs:
    if ctr_deco(r):
        P(f"{r['start']}-{r['end']}\t{r['qual']}\t{ctr_deco(r)[:120]}")

open(os.path.join(OUT, "_digest.txt"), "w", encoding="utf-8").write("\n".join(D))
print("\n".join(D[:45]))
print(f"... digest: {os.path.join(OUT,'_digest.txt')} ({len(D)} lines)")
json.dump(dict(defs=[{k: v for k, v in r.items() if k != 'calls'} for r in defs], n_keys=len(keys)),
          open(os.path.join(OUT, "_data.json"), "w", encoding="utf-8"), indent=0)
