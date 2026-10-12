# Fyah E.R. Integration Hardening Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Fyah Reverse Engineering command surface operational, safe, reproducible, and incrementally orchestrated with independently verifiable results.

**Architecture:** Keep the existing catalog as the initial registry, route the `fyah-re` entry point through the shared tools dispatcher, and add a versioned execution/result contract before introducing orchestration. Model output remains a proposal; deterministic policy authorizes; adapters execute; validators verify.

**Tech Stack:** Python 3.11+, argparse, pytest, existing `tools/` and `pipelines/` modules, GitHub Actions, local Qwen3/llama.cpp, REA MCP adapter.

## Global Constraints

- Preserve `feat/rea-mcp-integration-v1` and PR #1; do not merge automatically or push directly to `main`.
- No paid APIs, cloud model fallback, new persistent service, paid/large hosted runners, billing keys, or unapproved external execution. Keep the repository public and use only standard free `ubuntu-latest` runners; if free eligibility changes, stop rather than fall back to billable infrastructure.
- Do not claim a tool is operational unless its implementation and tests support that claim.
- Use test-first changes for behavior; record test and workflow evidence for each deliverable.
- Do not execute unknown binaries dynamically; static inspection and dynamic execution remain distinct capabilities.
- Treat model output as untrusted input; only allowlisted, schema-valid operations may reach the executor.

---

### Task 1: Replace the CLI placeholder with the shared dispatcher

**Files:**
- Modify: `fyah_re_cli.py`
- Modify: `tools/__main__.py`
- Modify: `tests/test_smoke.py`
- Create: `tests/test_cli_contract.py`

**Interfaces:**
- Consumes: `tools.__main__.main(argv=None) -> int`, existing `CATALOG` and `by_name`.
- Produces: `fyah-re list`, `fyah-re prompt`, `fyah-re run NAME --input PATH --out PATH`, and `fyah-re smoke --name NAME` using the existing dispatcher.

- [x] **Step 1: Define regression tests**
  - `list` returns code 0 and valid JSON array containing the catalog's `media-inspect` entry.
  - No subcommand raises argparse `SystemExit(2)`, not a false success.
  - An unknown tool raises a nonzero `SystemExit` with `ferramenta desconhecida` before attempting to open its input.
- [x] **Step 2: Implement the minimum behavior**
  - Delegate the installed entry point to the shared dispatcher.
  - Use `fyah-re` as the parser program name.
  - Reject unknown tool names and incorrect input arity before downloading inputs.
- [ ] **Step 3: Verify focused and full tests**
  - Run: `pytest -q tests/test_cli_contract.py tests/test_smoke.py`
  - Expected: all CLI contract tests pass; then `pytest -q` passes without disabling existing tests.
- [ ] **Step 4: Verify the PR CI workflow**
  - Run: existing `ci` workflow installs `.[audio,video,dev]` and runs `pytest -q`.
  - Expected: successful run on the implementation PR; record run URL and commit SHA.
- [ ] **Step 5: Commit and review**
  - Keep this deliverable on `work/fyah-er-integration-hardening-v1`; do not merge automatically.

### Task 2: Add execution contracts and evidence receipts

**Files:**
- Create: `tools/contracts.py`
- Create: `tests/test_execution_contracts.py`
- Modify: `tools/__main__.py`

**Interfaces:**
- Proposed `ExecutionReceipt` fields: schema version, run ID, UTC start/end, tool name/version, sanitized input metadata, SHA-256, status, exit code, output artifacts, duration, error category, and provenance.
- Each artifact record includes a relative path, byte size, and SHA-256; large binary payloads are never embedded in JSON receipts.

- [ ] Write tests for valid success, tool failure, malformed output JSON, missing output, and deterministic hash metadata.
- [ ] Verify each test fails against the current behavior.
- [ ] Implement the smallest contract and receipt builder; never record secrets or signed URL query values.
- [ ] Run focused tests and the full suite; verify the existing CLI JSON output remains backward compatible.
- [ ] Commit the independently passing deliverable.

### Task 3: Harden input acquisition and subprocess boundaries

**Files:**
- Modify: `tools/__main__.py`
- Create: `tests/test_input_safety.py`

**Interfaces:**
- Proposed `download(url, dest, *, max_bytes, timeout_seconds)` accepts local paths and HTTP(S) URLs under explicit size and time limits.
- Subprocess calls remain argument arrays with `shell=False`; each run uses a managed temporary directory.

- [ ] Add tests for unsupported URL schemes, missing local files, oversized responses, network timeout, invalid output, and cleanup after failure.
- [ ] Verify failing tests before changing implementation.
- [ ] Implement streaming download with byte ceiling, URL validation, finite timeout, cleanup, and clear nonzero failures.
- [ ] Run tests without external network dependence using a local HTTP fixture.
- [ ] Commit the independently passing deliverable.

### Task 4: Reconcile catalog, dependencies, and execution paths

**Files:**
- Modify: `tools/catalog.py`
- Create: `tools/inventory.py`
- Create: `tests/test_catalog_integrity.py`

**Interfaces:**
- Inventory output classifies each catalog item as implemented, partially implemented, missing dependency, or unavailable; it records module/kind, required inputs, extras, and test association.
- A catalog entry cannot be reported operational when its module or handler is missing.

- [ ] Test all catalog entries for a resolvable handler, declared input count, and required dependency extra.
- [ ] Verify tests expose missing/ambiguous catalog metadata.
- [ ] Add explicit catalog metadata and a deterministic JSON inventory command.
- [ ] Run focused tests, full suite, and compare inventory against actual package modules.
- [ ] Commit the independently passing deliverable.

### Task 5: Add validated multi-step orchestration

**Files:**
- Create: `tools/plan.py`
- Create: `tests/test_plan.py`
- Modify: `tools/__main__.py`

**Interfaces:**
- A versioned plan contains an allowlisted sequence/DAG of tool names, parameters, and references to prior output artifacts. It cannot contain shell commands or arbitrary Python.
- Execution results distinguish completed, failed, and blocked steps. Required-step failure returns nonzero.

- [ ] Test invalid tool, malformed plan, cycle, missing artifact reference, failed dependency, and successful two-step flow.
- [ ] Verify each invalid plan is rejected before any tool executes.
- [ ] Implement schema validation, cycle detection, artifact handoff, and aggregate receipt.
- [ ] Add an E2E using two compatible real tools on a tiny repository fixture.
- [ ] Commit the independently passing deliverable.

### Task 6: Strengthen Qwen3 + REA MCP decision evidence

**Files:**
- Modify: `harness/rea_dsh_adapter.py`
- Modify: `.github/workflows/er-harness.yml`
- Create: `tests/test_rea_receipt_validation.py`

**Interfaces:**
- Model proposal, deterministic policy decision, actual MCP invocation, fixture identity/hash, and normalized result are separate receipt fields.
- Only the repository-generated authorized fixture and the explicit `inspect_artifact` operation may be called in decision mode.

- [ ] Test approval, denial, malformed model response, MCP unavailable, invalid fixture path, and forbidden operation.
- [ ] Verify negative cases fail closed and never call MCP.
- [ ] Validate receipt schema and cross-check actual MCP response with fixture digest.
- [ ] Run E2E with Qwen3 and retain sanitized receipt and artifact digest.
- [ ] Commit the independently passing deliverable.

### Task 7: Publish verification and investigation evidence

**Files:**
- Create: `docs/ferramentas/INTEGRATION_STATUS.md`
- Modify: `.github/workflows/ci.yml`
- Modify: relevant workflow summaries

**Interfaces:**
- CI summary reports commit, test counts, workflow/run IDs, artifact hashes, failed/blocked steps, and limitations.
- Status labels distinguish implemented, unit-tested, integration-tested, E2E-proven, partial, and unavailable.

- [ ] Test summary generation for pass, failure, and partial execution.
- [ ] Verify missing evidence cannot produce an E2E-proven status.
- [ ] Add concise summaries and upload sanitized evidence artifacts.
- [ ] Run full CI and the required E2E workflows; link receipts in status documentation.
- [ ] Commit the independently passing deliverable.

## Unresolved external decisions

- Whether a future orchestrated plan may continue independent branches after one branch fails; initial recommendation is to block dependent steps and allow unrelated independent steps to continue, while returning nonzero if any required step fails.
- Whether to keep legacy direct workflow dispatchers indefinitely; initial recommendation is to preserve them until parity tests prove the shared executor can replace them.
