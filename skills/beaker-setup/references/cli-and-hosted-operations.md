# CLI and hosted operations

## Onboarding loop

Before entering the loop, authenticate and run `beaker agent list --json`
through `uvx --from beaker-sdk` when Beaker is not installed in the project.
Match the current GitHub repository. If a matching agent exists, select its
repository-relative `beaker_config_path`, read that YAML's Git-root-relative
`spec.source_dir`, and run the loop from that project with the same config
selector. Only initialize a config after discovery establishes that no
applicable agent/config exists. Status searches upward and does not discover a
nested config below the Git root.

Run `beaker onboarding status` after every command and whenever the next
action is uncertain. Follow its one returned action. The ordered state checks
are `beaker_dependency_declared`, `config_present`, `logged_in`,
`github_connected`, `agent_selected`, `spec_integrated`, `tracing_wired`,
`integration_pushed`, `dataset_available`, and `experiment_launched`. Onboarding is
complete once `experiment_launched`
is complete. Shipping a winning candidate pull request is developer-owned
follow-up work outside the onboarding loop.
`github_connected` checks only the organization's GitHub App installation;
`agent_selected` also requires a selected agent with a non-empty repository
association that the App can read.

Use `beaker onboarding status --json` for automation:

- The response contains `steps`, `next`, `blocked_on_developer`, and
  `errors`; every step contains `id`, `state`, `reason`, `owner`,
  `next_action`, and `blocking`, while `next` contains `id`, `owner`, and
  `action`.
- The next action is the first incomplete agent-owned step in canonical
  order. If no agent step remains, `next` is the first known-incomplete
  developer-owned step.
- Relay only newly discovered actions in `blocked_on_developer` verbatim to
  the developer without attempting them, and track which actions were already
  reported in this session. This report is not a halt: continue with the
  returned `next.action`.
- An `unknown` step has not been checked yet and never means that the
  developer must act. Offline or logged-out hosted checks are reported as
  `unknown`; run `beaker login` when it is the returned action.
- Stop and wait only when `next` itself is developer-owned.
- Exit `0` means the state and an actionable `next` were computed, including
  incomplete onboarding. Selection and hosted errors remain in `errors` but
  return `0` when `next` is actionable.
- Exit `2` is reserved for a not-computed payload where an actionable `next`
  could not be produced. On exit `2`, read `errors`, retry once, and if it
  persists relay the error to the developer.
- When onboarding is complete, `next.id` is `null` and `next.action` contains
  the completion message.
- Tracing is optional and advisory (`blocking: false`): when tracing is
  included, make a best effort to commit its wiring with the integration, but
  never let it delay the required push.
- `integration_pushed` verifies that the current local commit is present on a
  branch in the selected agent repository; it is required before a hosted
  optimization run, not before dataset upload. Perform that commit and push
  without asking the developer to confirm, unless the developer told you not to
  take autonomous actions, on a `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch; a
  checkout sitting on `main`, `master`, `trunk`, or `develop` gets that branch
  suggestion in the step reason instead of being pushed as-is. The agent
  normally completes the later `dataset_available` and `experiment_launched`
  steps too, but the developer may also complete them, including through the
  platform UI.

## GitHub App access

- `beaker github status` reports the organization's GitHub App installation
  without opening a browser. `--repo <owner/name>` also checks that this
  installation can read that repository. Exit 0 connected, 1 missing, 2 error.
- `beaker github connect` installs the app for the organization. `--repo` is
  optional and only verifies a repository after connecting; repository selection
  happens in GitHub's picker.
- Connect opens the install page and polls until the installation appears,
  waiting up to `--timeout` seconds (default 600). Relay the printed URL when
  the browser cannot open, and leave the command running.
- Installing the app requires an organization admin. A non-admin receives
  `connecting GitHub requires an organization admin`; that is a handoff, not a
  retryable error.
- `beaker agent setup --repo <owner/name>` and `beaker agent create` run the
  same flow implicitly. Check `beaker github status` first so the browser step
  is expected.
- On `timed out waiting for GitHub access to <repo>`, re-run `beaker github
  connect --repo <owner/name>` rather than re-running agent setup.

## Authentication and agent selection

- `beaker auth status` checks the user-level login; `beaker login` creates it.
- After login, run `beaker agent list --json` before setup or creation. Filter
  its `agents` by an exact `github_repository` match with the current GitHub
  checkout. Each matching record's `beaker_config_path` is the authoritative
  repository-relative YAML selector. Most new users will not have an agent yet.
  If none matches this repository, confirm what they want to optimize and
  create one with a clear name for that target.
- If one existing agent clearly matches the task, use it. If several agents
  could match, ask the developer which one to use. State which agent you
  selected.
- `beaker agent setup "<selected-agent>"` selects an existing optimization
  target and writes `BEAKER_API_BASE_URL`, `BEAKER_API_KEY`, and
  `BEAKER_AGENT_KEY` to `.beaker/.env`. Pass `--repo <owner/name>` only when the
  existing target needs a repository association.
- An unknown name passed to `beaker agent setup` creates a target. Only do this
  after discovery finds no suitable agent or the developer explicitly chooses
  a different agent; creation requires `--repo <owner/name>`.
- Selection precedence is explicit `--agent`/`--agent-key`, then `BEAKER_AGENT_KEY`, then `agent_key` in `.beaker/beaker.yaml`.
- Agents represent optimization targets, not repositories. Agent setup discovers the selected YAML and stores it on the agent as `beaker_config_path`, relative to the Git root. Rerunning setup synchronizes this value for an existing repository-associated agent; pass `--repo` when selecting an unassociated agent so setup can associate it and store the path.
- Archived agents retain history and released prompt serving but reject new changes. Their keys cannot be reused; choose a different target name.

Do not ask the developer to paste API keys when CLI login is available. `BEAKER_AGENT_KEY` is an agent selector, not a credential-bound API key.

Organization admins can use the user-level login to edit an active agent's mutable metadata without rewriting repo-local credentials:

```bash
beaker agent edit "<selected-agent>" --name "<New Name>"
beaker agent edit "<selected-agent>" --config-path services/invoices/.beaker/beaker.yaml
```

At least one of `--name` or `--config-path` is required. The agent key and GitHub repository cannot be changed with `agent edit`; `--config-path` must be relative to the Git root.

## Config location and monorepos

The default config is `.beaker/beaker.yaml` under the selected project root.
Discover existing agents before initialization. When none applies, enter the
chosen project root and use the same config selection for every command. Run
agent setup there so `.beaker/.env` is written beside the selected project:

```bash
uvx --from beaker-sdk beaker auth status
uvx --from beaker-sdk beaker login  # only when auth status requires it
uvx --from beaker-sdk beaker agent list --json

# No existing agent/config matched, so initialize the chosen project.
cd services/invoices
uvx --from beaker-sdk beaker init

# Install the project dependency with the command printed by init, then:
beaker github status --repo acme/invoices
beaker agent setup "Invoice Extraction" --repo acme/invoices

# Or choose another location inside this project:
beaker --config-file config/beaker.yaml init
beaker --config-file config/beaker.yaml agent setup "Invoice Extraction" --repo acme/invoices
```

After adding Beaker to the project, omit `uvx --from beaker-sdk` and use the
project's ordinary `beaker` command.

`BEAKER_CONFIG_FILE` is equivalent to `--config-file`. The CLI converts the
discovered location to a Git-root-relative `beaker_config_path`, such as
`services/invoices/.beaker/beaker.yaml`, when creating or selecting the agent.
The selected YAML's `spec.source_dir` is also Git-root-relative, so a nested
project records `source_dir: services/invoices`; `package_import_root` remains
relative to that source directory. Local smoke and hosted GitHub builds use
this same base. `source_dir: "."` means the Git root even when the YAML is
nested; it does not mean the directory containing the YAML. Absolute paths and
paths containing `..` are rejected. If smoke or onboarding reports `Set
source_dir to services/invoices`, apply that exact repository-relative value to
the existing config and rerun the check.
If a later command runs from the Git root, pass that full repository-relative
path as its selector. Paths must remain inside the Git repository. Agent setup
writes `.beaker/.env` under its working directory, so run it from the intended
project root when credentials should live beside that project's config.

## Beaker YAML preflight

Before hosted validation or launch, inspect the selected `beaker.yaml` against
the committed repository. Do not assume generated or previously working values
still match the checkout:

```yaml
spec:
  target: "beaker_spec:build_spec"
  source_dir: "services/example"
  package_import_root: ".beaker"
  required_env:
    - DATABASE_API_KEY
```

Check each field that controls the hosted evaluator:

- Resolve `spec.source_dir` from the Git checkout root. It defaults to `.`, so
  in a monorepo set it to the package or service directory rather than
  assuming the Git root is the project root.
- Resolve `spec.package_import_root` inside `spec.source_dir`, and check that
  the resulting directory exists in the pushed commit. Do not read it relative
  to wherever the local CLI happens to run. Both fields are optional, and
  `beaker init` writes them only when they differ from the defaults, so add
  them only when the layout needs them.
- Install the evaluator's dependencies from the pushed bundle. When
  `spec.source_dir` contains a `pyproject.toml`, the hosted image installs that
  package and its dependency closure. Otherwise list every runtime dependency
  in `spec.pip_install` and system packages in `spec.apt_install`. A dependency
  that exists only in the local environment fails the image build or the first
  import inside the evaluator.
- Derive `spec.required_env` from variables read by code that runs in the
  candidate evaluator child process. The list is an allowlist: storing a value
  in agent settings does not expose it unless its name is declared here.

Commit and push changes to these fields before launch so the hosted spec build
reads them. Runs are immutable snapshots: changing YAML or agent settings does
not repair an existing failed run, so start a new run after correcting either.
A passing structural smoke check does not prove that the hosted image builds,
that `run_case` executes, or that an environment value reaches the child
process.

Paths inside the selected spec table use hosted checkout coordinates:

- `source_dir` is relative to the Git checkout root, regardless of where the
  YAML lives;
- `package_import_root` is relative to `source_dir`; and
- `target` is imported from `package_import_root`.

For this nested layout:

```text
repo/
  services/invoices/
    pyproject.toml
    .beaker/
      beaker.yaml
      beaker_spec.py
```

use:

```yaml
spec:
  target: beaker_spec:build_spec
  source_dir: services/invoices
  package_import_root: .beaker
```

Validate the hosted coordinate system from the Git root, carrying the full
config selector and using the nested project's environment. With uv, for
example:

```bash
uv run --project services/invoices beaker \
  --config-file services/invoices/.beaker/beaker.yaml \
  run smoke --strict --agent <agent> --dataset <name@revision>
```

Running from the project root with its default config selects the same file;
either working directory works when the selector resolves to the selected
YAML.

## Common integration failures

The `source_dir` rows below all stem from the Git-root-relative resolution
described in [Config location and monorepos](#config-location-and-monorepos).

| Error or symptom | Cause | Fix |
|---|---|---|
| `Configured source_dir is not a directory in the GitHub checkout: '<path>'` | `source_dir` was written relative to the YAML, current directory, or package rather than the Git root. | Set `source_dir` to the project directory as seen from the repository root, commit, push, and launch a new run from that branch. |
| `Configured package_import_root is not a directory in the GitHub checkout: '.beaker'` | A nested project used `source_dir: .`, so hosted resolution searched for repository-root `.beaker`. | Set `source_dir` to the Git-root-relative project path and keep `package_import_root: .beaker` when the spec file is under that project's `.beaker/`. |
| `could not find source for target ...` or `ModuleNotFoundError` while loading the spec | `target` is not importable from `package_import_root`, or a path component is not a Python identifier. | Resolve the target as `module.path:callable` from the configured import root; adjust the import root or module path without moving Beaker policy into application source. |
| Hosted build cannot import application dependencies even though local smoke loads the spec. | `source_dir` does not point at the project containing `pyproject.toml`, so the image builder does not install that package. | Point `source_dir` at the nested Python project, or declare only genuinely external build requirements through the supported image dependency fields. |
| `Package '<name>' requires a different Python: 3.12.x not in '>=3.13'` during image build | Hosted images default to Python 3.12, but the selected project's `requires-python` excludes it. | Set `spec.environment_base: debian_slim:3.13` (or another supported version satisfying the project), commit, push, and launch a new run. Do not weaken the project's Python requirement merely to satisfy the default image. |

After any hosted failure, inspect it with `beaker run status <run-id>`, fix the
root cause rather than retrying the same immutable commit, push the fix, launch
a new run, and monitor it with `beaker run status <new-run-id> --watch`.

## Hosted environment variables

### Credential preflight

Before a hosted launch, derive credential requirements from every application
path that `Spec.run_case` can reach. Include SDK defaults and fallback branches
that can run when a selected model or provider route is absent. Do not rely
only on names already present in `spec.required_env`. Read the application
source to collect the variable *names* it reads; this inspection never reads,
prints, or copies a secret value. Search the first-party source paths,
adjusting them to this repository's layout:

```bash
rg -n 'os\.environ|os\.getenv' .beaker <application-source-dir>
```

Classify each credential before configuring it:

- When candidate application code reads an environment variable directly,
  declare its name in `spec.required_env` and store its hosted value in the
  selected agent's encrypted environment settings.
- Calls routed through `inference_target(runtime)` or
  `scoring_inference_target()` need no credential setup. Do not declare a
  provider key for them, do not create an agent or organization provider key,
  and do not block a launch on one being absent. With no agent or organization
  key configured, the gateway selects the platform key, which covers OpenAI,
  Anthropic, Google, and OpenRouter. Agent and organization keys are a billing
  choice the customer makes in the UI.
- Before declaring a provider key, check whether the gateway can serve that
  call instead. Route what it can serve through `inference_target(runtime)` and
  leave that key out of `spec.required_env`; see
  [model-routing-and-tracing.md](model-routing-and-tracing.md).
- A call site the gateway cannot serve still needs its own key declared and
  set, even when other calls in the same run are gateway-routed.

Treat process environment variables and values in `.beaker/.env` as local
only. Beaker does not copy them to hosted settings. Immediately before launch,
run `beaker agent env list --agent <selected-agent>` and stop if a required
name is absent. Structural smoke does not execute `run_case`, so it cannot
validate these credentials. Set any missing value with the commands below, then
list the names again before launch.

Declare application variables needed by candidate evaluation as names under the
selected YAML spec. Values never belong in YAML:

```yaml
spec:
  target: beaker_spec:build_spec
  required_env:
    - DATABASE_URL
    - SERVICE_TOKEN
```

Use uppercase POSIX-style names. A declaration may contain at most 50 unique
names. `BEAKER_*`, runtime-control names such as `HOME`, `PATH`, and `PYTHONPATH`,
and platform routing names such as `OPENAI_BASE_URL` are reserved
and rejected. Every declared value is available to the candidate application
during evaluation. Declare only values that the application actually needs,
and prefer evaluation-scoped, least-privilege credentials with narrow access
and a limited lifetime. Do not reuse production administrator, owner, or root
credentials for candidate evaluation.

Local values may live in the selected project's `.beaker/.env`. Repository-local
values do not become hosted runtime secrets. Manage hosted values explicitly:

```bash
beaker agent env list --agent <selected-agent>
printf '%s' "$DATABASE_URL" | beaker agent env set DATABASE_URL --value-stdin --agent <selected-agent>
beaker agent env delete DATABASE_URL --agent <selected-agent>
```

Use `--value-stdin`, not `--value`, so the secret does not enter shell history.
Beaker lists names and non-revealing hints only and never returns plaintext
values. Never log or commit secret values.

At dispatch, Beaker copies only declared customer variables into each candidate
evaluator. A missing or empty `required_env` value fails the run before
candidate code starts. Set the value, verify its name with `beaker agent env
list`, and start a new run; do not retry the failed run unchanged.

## Hosted data and run ordering

1. Ensure the target agent exists and that `beaker github status --repo
   <owner/name>` reports the repository as readable. If it does not, have the
   developer run `beaker github connect --repo <owner/name>` before continuing.
2. Upload and inspect the dataset:

   ```bash
   beaker dataset upload <dataset-dir> --name <dataset-name> --total-count <n> --split train=<n> --split val=<n> --agent <selected-agent> --json
   beaker dataset list --agent <selected-agent>
   beaker dataset show <dataset-name> --agent <selected-agent>
   ```

   The upload command requires a directory or JSONL file path. If a conversion
   script generates that input, it must use an OS-managed temporary directory
   rather than a path in the repository. Run `beaker dataset upload`
   synchronously before the temporary directory is removed. Existing
   source-of-truth dataset directories may be uploaded from their established
   locations without being copied. Preserve the upload response's
   `dataset_revision` and `artifact_id`; they identify the immutable snapshot.

3. Validate that exact hosted snapshot through the same download path used by
   optimization:

   ```bash
   beaker run smoke --strict --agent <selected-agent> --dataset <dataset-name@revision>
   # Or, equivalently:
   beaker run smoke --strict --agent <selected-agent> --dataset-id <artifact-id>
   ```

   Supply exactly one selector. Remote smoke authenticates and downloads the
   dataset through presigned URLs, but does not execute a rollout or scorer and
   does not launch a hosted run. A configured `config_defaults.dataset_ref` or
   `config_defaults.dataset_id` can supply the selector when it names this same
   snapshot.

4. Trigger only with explicit developer authorization, reusing the selector
   that passed smoke:

   ```bash
   beaker run trigger --agent <selected-agent> --dataset <dataset-name@revision>
   # Or use --dataset-id <artifact-id> instead.
   ```

   The first run always uses this plain command. Do not add optional run-type
   flags such as `--optimization-model`, `--execution-mode`, or
   `--test-all-candidates`.

   Before triggering, commit and push the completed integration yourself, to
   the `beaker/<YYYYMMDD-HHMM>-<agent-name>` branch you intend to use. Do not
   stage secret files.

   Without `--ref`, the CLI uses the current checked-out branch when it belongs
   to the linked repository and exists on its remote, then falls back to the
   repository's GitHub default branch. Pass `--ref <remote-branch>` only for an
   explicit remote branch override. Tags and commit SHAs are rejected with
   `422` because hosted sources must be branches that can serve as pull-request
   bases. The command prints the current branch when selected locally, or
   `default branch` when the server selects the fallback.

Trigger defaults to `.beaker/beaker.yaml`. Run it from the same project root
used for setup, or carry the same `--config-file` or
`BEAKER_CONFIG_FILE` selection through. The stored `beaker_config_path` lets
hosted operations resolve the same nested YAML.

Use the same selected agent for dataset inspection, upload, and launch.

Dataset uploads create immutable revisions and normally promote the new
revision to `production`. Re-uploading identical files is a no-op. Bare names
resolve the production alias at command time, so use `name@revision`, artifact
id, `config_defaults.dataset_ref`, or `config_defaults.dataset_id` when smoke
and launch must use the same snapshot. Explicit `--dataset` and `--dataset-id`
selectors override configured selectors and must not be combined. Never expose
storage URIs.

Preserve the full run UUID and the `View in UI:` link printed by trigger. Use
`beaker run status <full-run-id>` for a one-shot check; exit code 3 means the
run is still active. Add `--watch` only when polling is intended. Use
`beaker run pull <full-run-id>` for results.
