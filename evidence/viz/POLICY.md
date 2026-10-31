# POLICY: the visual-engine page may carry script, R2 is unchanged for every page `emfit/webapp.py` serves

**Status: a ruling, made deliberately, on `docs/design/visual_engine_arch.md` §9.6 option 3.**
It overrules **R2** as that ruling is worded for pages served by *a different handler*, and it leaves
R2 standing, unchanged and binding, for every page `emfit/webapp.py` serves. It is written as an
evidence note because it is a *policy* artefact, not a code change: **no code is changed by this
document and no route is added by it.** Its machine-checkable half is one assertion in
`tests/test_demo_picker.py` (`_no_script`, §3(d)).

Marks: **[M]** measured against a file in this tree; **[L]** read from a named file and cited there.

## 1. The ruling being overruled, quoted verbatim

`docs/design/visual_engine_arch.md` **L417**, §11 row 8 [L]:

> | 8 | Whether a page may execute script | **RULED (R2): it may not**, on any page this front end serves, and any artefact it serves must render without script. Guard condition: the ruling binds the served pages and not the engine, so a page from a different handler is out of scope and must say so (9.6, 8.6) | 9.6, and the shape of the MVP |

and the prose that row condenses, **L366-367**, §9.6 [L]:

> It is **ruled** at Dispatch 43: **R2, the script policy, stands, and a page served by this front end does not execute script.** A client-side viewer is therefore not admissible on any page this front end serves, and the three ways out below are reduced to the ones that do not change the policy. **The guard condition matters as much as the ruling.** R2 binds the pages this handler serves (`emfit/webapp.py:359`, `do_GET` at `:432`), not the visual engine and not the artefact: a viewer that renders without script is admissible anywhere, and a page produced by a different handler, outside this front end, is outside this ruling and must say so where the artefact is generated (8.6).

Two clauses have to be read separately, because the ruling itself separates them:

- **The binding clause.** A page *this front end serves* does not execute script. That clause is touched
  by nothing here — see §3(c).
- **The guard clause.** The ruling binds *the served pages*, not the engine and not the artefact; a page
  produced by a **different handler** is *out of scope* and *must say so*. That clause is what the
  current structure of the repository has made untestable, and it is the clause this policy uses.

## 2. The authority for changing it

R2 is a policy, and the document that made it names the way to change it. **L370**, §9.6 option 3 [L]:

> 3. **Change the policy.** Allowed, deliberate, and a ruling. The docstring's "a page is not exempt" is the sentence that makes it a ruling rather than a test edit.

The distinction matters and is preserved: this is **not a test edit**. `_no_script` is not weakened and
no call site is removed — see §3(d). It is a policy change, recorded as one, with the losing reading
quoted in full at §1 so that the reversal can be audited from either side.

## 3. The policy

**(a) A visual-engine page MAY carry script.** A page whose purpose is an interactive view of a
computed structure may execute JavaScript, may load a library, and may make the interaction the
motivation for building it. This is the deliberate change: the earlier ruling priced interaction out
of every page, which reduced the MVP to "a better PNG" (§9.6 option 1, L368) and is why a ruling is
needed rather than a preference.

**(b) It must be a page served by a DIFFERENT handler, not by this front end, and the page must say so.**
Concretely: not `emfit/webapp.py`'s one-response path. The page must (i) be produced by a handler
that is not `emfit/webapp.py`, and (ii) carry, on the page itself, a statement that it is outside this
front end's script policy and what that means for the reader (that it may not render without script,
and that it is not part of the study pages). The "must say so" half is not optional decoration: the
guard condition in §1 requires it, and it is the only thing that distinguishes this page from a served
study page to a reader who arrived by URL.

**(c) R2 continues to bind every page `emfit/webapp.py` serves — all of them, unchanged.** The landing
page, the demo picker, the study pages, the run responses, the 400s and the 404s are script-free, stay
script-free, and are asserted so. Nothing in (a) or (b) is an exemption for any of them, and a page
served by `emfit/webapp.py` that executes script is **still a defect**, not a new-policy page.

**(d) The machine-checkable half.** `tests/test_demo_picker.py` keeps `_no_script` (L96-100 after this
dispatch's edit, L96-98 before it) [M] and all five call sites (L124/154/171/189/207 after the edit;
L122/152/169/187/205 before it) [M], and gains one assertion: `_no_script` now also asserts that the
literal CDN shape `://cdn.` appears nowhere in the body. That assertion is **narrower than the sentence
that motivates it** — it catches a CDN URL of that shape, not every off-host URL a page could name, and
the comment above it says so rather than implying more — and it is narrower than "no script" on
purpose: the (a)/(b) page is allowed to be script-bearing, so the test cannot be extended to every
page; what it pins is that the pages **this handler serves** do not execute script and do not carry a
`://cdn.` reference.

## 4. The contradiction this policy has to own

§9.6 option 2 (L369) says the "outside the front end" escape route does not survive contact with the
code [L]:

> 2. **Put the viewer on a page outside the front end's policy.** This one does not survive contact with the code: every response is served by the same handler (`emfit/webapp.py:359`, `do_GET` at `:432`, `do_POST` at `:472`), so there is no outside.

That is true **today**, and it is the reason clause (b) is written as a *precondition on a future
handler* rather than as a description of an existing one. Read against the code, the guard clause and
option 2 are in tension: the guard clause presumes a second handler can exist, option 2 observes that
none does. Both statements are recorded here instead of one being quietly dropped. The resolution this
policy adopts is the narrow one: **the guard clause defines a boundary; it does not create the thing on
the far side of it.** Until a different handler exists, clause (b) has no instance, and this policy
therefore authorises *no page that exists*.

## 5. Honesty clause: there is no static-file route, and this policy does not add one

This policy is a licence for a page, and it is **not** a licence to add a route. The facts, because the
tempting next step is "add one line to `do_GET`" and that would be a different decision:

- `emfit/webapp.py`'s own docstring says the server is *"deliberately tiny: `http.server` from the
  standard library, one request at a time … every page rendered as a single self-contained HTML
  document: the study's PNG figures *and* any animated attachment it produced … are inlined as
  `data:` URIs -- so there is **no static-file route**, no temp directory and nothing to leak between
  runs"* [L, L4-9].
- The whole route table is **six** GET paths and one POST path [M]: `do_GET` at L432 with `/healthz`
  (L435), `/favicon.ico` (L437), `/` (L439), `/demo` (L441), `/s/…` (L454) and `/run/…` (L462), and
  `_not_found()` for everything else (L470); `do_POST` (L472) serves `/run/` only. **There is no route
  from which a script or a library could be served.**
- Delivery is fixed to one response: `Content-Length` is set (L373) and `Cache-Control: no-store`
  (L374) [M], and §8.1 (L256) + §8.4 (L270) derive from `decisions.md:13` that the browser fetches
  nothing afterwards — "no CDN and no relative `src` to a server route can supply a renderer library"
  [L, L270].

Therefore: **this policy authorises a future handler and a future page, and it authorises nothing
today.** A dispatch that wants the script-bearing page must also authorise the handler, the route it
is served from and the byte budget for it; none of that is granted here, and none of it should be read
into this file. The one thing this file changes today is the test assertion in §3(d).

## 6. What this policy does not do

1. **It does not weaken `_no_script`.** No assertion is removed, no call site is dropped, and the
   `b"<script"` assertion is untouched.
2. **It does not add a route, a handler, a static directory, a CDN reference or a vendored library.**
3. **It does not overrule R1, R3 or any other ruling** in `docs/design/visual_engine_arch.md` §11; rows
   5 and 8 are the only ones it touches and it touches row 8 only as worded for *served* pages.
4. **It does not re-open the byte budget** (§8.3) or §8.4's derivation, both of which continue to
   govern any artefact `emfit/webapp.py` serves.
5. **It does not make a client-side viewer admissible on any study page**, now or later; that reading is
   the one R2 forbids and clause (c) keeps.

## 7. What would void it

A page produced by a handler that is `emfit/webapp.py` under another name; a page that omits the
"outside this front end's script policy" statement; or an attempt to serve a vendored library through
the webapp's one-response path and call it "a different handler". Any of those returns the page to R2,
and the page becomes the defect R2 says it is.

## 8. Provenance

Quotations in §1, §2 and §4 are verbatim from `docs/design/visual_engine_arch.md` at the line numbers
given, re-read for this policy [M]. The route table in §5 was read from `emfit/webapp.py` at the line
numbers given [M]; the docstring sentence is quoted from L4-9 [M]. The five `_no_script` call sites are
`tests/test_demo_picker.py` L124/154/171/189/207 after this dispatch's one-assertion edit, and
L122/152/169/187/205 before it [M]. Nothing in this file is a measurement of a page,
because no script-bearing page exists to measure.
