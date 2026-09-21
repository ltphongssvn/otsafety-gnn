# Schema-first contracts — the two-axis rule (Pydantic SSOT + Zod at the boundary)

Adapted from FleetManagement's `context/schema-first-zod-contracts.md` for a
repository with Python producers and a TypeScript consumer.

## Governing rule — do not conflate the axes

**Axis 1 — runtime validation is governed by the trust boundary.**
Untrusted or external input is validated where it enters: files on disk, HTTP
bodies, env vars, subprocess and third-party JSON. Python validates with
`Model.model_validate(_json)`; TypeScript with `Schema.parse` / `safeParse`.
Data our own code already produced and typed is *not* re-validated.

**Axis 2 — shape definition is governed by duplication.**
A shape that crosses a boundary, or would be written in more than one place, has
**one** definition. Everything else derives from it. An internal, single-use,
non-duplicated shape stays a plain type — never force a schema onto it.

**Exactly three fix-triggers:** (1) boundary input with no validation; (2) the
same shape defined twice, or hand-written where a schema exists; (3) the
converse — no schema forced onto internal-only, non-duplicated shapes.

## Across the language boundary: Pydantic is the source

The Python contracts *produce* every record, so they own the shape.

```
Pydantic model  ──contracts:generate──▶  contracts/json/<name>.<v>.schema.json  (committed)
                                          │
                        json-schema-to-zod (pinned)
                                          ▼
                     apps/site/src/contracts/<name>.<v>.gen.ts  (committed, never edited)
                                          ▼
          readRecords(dir, Schema): Schema.safeParse per file; types = z.infer
```

The exported schema describes **what producers write**, not what Pydantic would
accept: references inlined (json-schema-to-zod turns a `$ref` into `z.any()`),
every property required, no defaults (a default becomes `.default()`, which fills
a missing field instead of rejecting it). Cross-field invariants stay in the model
validators; the producer enforces them on write, the site checks shape on read.

**Drift gates:** `test_contract_schemas.py` (model ↔ committed JSON Schema) and
`test_contract_boundary.py` (JSON Schema ↔ committed Zod; and a malformed record
must fail the build, naming its file).

## Canonical enum pattern

TypeScript: one `as const` array → `type X = (typeof A)[number]` and `z.enum(A)`.
Pass the array directly, never a loosely typed variable, or inference collapses
to `string`. Python: one `Literal[...]` (or `StrEnum`) used as the field type;
it exports as a JSON Schema `enum` and arrives in the site as `z.enum`.

## Case study — the evidence page (2026-09-20)

`apps/site/src/data/evidence.ts` hand-wrote `SettingsCheck` beside
`SettingsCheckReport` and read each file with `JSON.parse(...) as T`. Four of five
fields had drifted: `recorded_at`, `rule`, `code`, `detail` against the real
`generated_at`, `rule_id`, `reason_code`, `message`. Production rendered the real
failing verdict as "fail" and nothing else; a `?? ""` in the template hid it. The
test fixtures matched the TypeScript type rather than the contract, so every test
passed — the run fixture was even invalid, a failure with no `error_type`. The page
meanwhile claimed a record off its contract fails the build.

Fixed: the pipeline above; readers parse at the boundary; fixtures are built from
the Pydantic models; the drifted shape itself is a test that must fail the build.
All 182 real records passed the strict schemas — the producers were always right.

## Audit backlog (record here; fix when in domain)

- **P1 — `toolchain.json` entry shape.** Read as `dict[str, Any]` by
  `test_render_image.py`, `test_railway_pin.py`, `test_site_deploy.py`, and by
  `flake.nix` and `bootstrap_toolchain.py`. Inspect whether a model exists; if not,
  one Pydantic model for an entry, used by every Python reader.
- **P2 — `pr.required_checks()`** reads workflow YAML by raw dict access. A
  repository-owned file, but a file payload: inspect before classifying.

## Explicitly not violations

The one-pager's tables in `scripts/build_arch_onepager.py` (internal, single use);
`scripts/check_site.py` (status codes only); `pr.py`'s `Check`, `PullRequest` and
`MergeResult`, which already validate gh's JSON at the boundary.
