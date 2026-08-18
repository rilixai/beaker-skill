# CLI and hosted operations

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
- After login, run `beaker agent list` before setup or creation. Most new users
  will not have an agent yet. If none exists, confirm what they want to optimize
  and create one with a clear name for that target.
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

## Scopes (only when the developer asks)

Only consult this section when the developer explicitly asks about scope
isolation. For a normal setup, leave `scope_key` absent or unset in
`beaker.yaml` and omit `--scope-key`. Beaker then uses the selected agent's
default scope. Never add a scope merely because setup is being run from another
repository, config path, spec, or task, and do not raise the topic yourself.

If the developer explicitly chooses to add a scope to an existing agent, ask
for or confirm its stable key. Configure it persistently with `scope_key` in
`beaker.yaml`, or use `--scope-key <scope-key>` only for the relevant run.

Organization admins can use the user-level login to edit an active agent's mutable metadata without rewriting repo-local credentials:

```bash
beaker agent edit "<selected-agent>" --name "<New Name>"
beaker agent edit "<selected-agent>" --config-path services/invoices/.beaker/beaker.yaml
```

At least one of `--name` or `--config-path` is required. The agent key and GitHub repository cannot be changed with `agent edit`; `--config-path` must be relative to the Git root.

## Config location and monorepos

The default config is `.beaker/beaker.yaml` under the selected project root.
Enter that root first, then use the same config selection for every command:

```bash
cd services/invoices
beaker init
beaker login
beaker github status --repo acme/invoices
beaker agent list
beaker agent setup "Invoice Extraction" --repo acme/invoices

# Or choose another location inside this project:
beaker --config-file config/beaker.yaml init
beaker agent list
beaker --config-file config/beaker.yaml agent setup "Invoice Extraction" --repo acme/invoices
```

`BEAKER_CONFIG_FILE` is equivalent to `--config-file`. The CLI converts the
discovered location to a Git-root-relative `beaker_config_path`, such as
`services/invoices/.beaker/beaker.yaml`, when creating or selecting the agent.
If a later command runs from the Git root, pass that full repository-relative
path as its selector. Paths must remain inside the Git repository. Agent setup
writes `.beaker/.env` under its working directory, so run it from the intended
project root when credentials should live beside that project's config.

## Hosted environment variables

Repository-local environment values do not become hosted runtime secrets. Manage required provider or application variables explicitly:

```bash
beaker agent env list --agent <selected-agent>
printf '%s' "$OPENAI_API_KEY" | beaker agent env set OPENAI_API_KEY --value-stdin --agent <selected-agent>
beaker agent env delete OPENAI_API_KEY --agent <selected-agent>
```

Beaker lists names and hints only and does not return plaintext values. Never log or commit secret values.

## Hosted data and run ordering

1. Ensure the target agent exists and that `beaker github status --repo
   <owner/name>` reports the repository as readable. If it does not, have the
   developer run `beaker github connect --repo <owner/name>` before continuing.
2. Upload and inspect the dataset:

   ```bash
   beaker dataset upload <dataset-dir> --name <dataset-name> --total-count <n> --split train=<n> --split val=<n> --agent <selected-agent>
   beaker dataset list --agent <selected-agent>
   beaker dataset show <dataset-name> --agent <selected-agent>
   ```

   The upload command requires a directory or JSONL file path. If a conversion
   script generates that input, it must use an OS-managed temporary directory
   rather than a path in the repository. Run `beaker dataset upload`
   synchronously before the temporary directory is removed. Existing
   source-of-truth dataset directories may be uploaded from their established
   locations without being copied.

3. Trigger only with explicit developer authorization:

   ```bash
   beaker run trigger --agent <selected-agent> --dataset <dataset-name>
   ```

   Without `--ref`, the CLI uses the current checked-out branch when it belongs
   to the linked repository and exists on its remote, then falls back to the
   repository's GitHub default branch. Pass `--ref` only for an explicit
   override. The command prints the current branch when selected locally, or
   `default branch` when the server selects the fallback.

Trigger defaults to `.beaker/beaker.yaml`. Run it from the same project root
used for setup, or carry the same `--config-file` or
`BEAKER_CONFIG_FILE` selection through. The stored `beaker_config_path` lets
hosted operations resolve the same nested YAML.

Use the same selected agent for dataset inspection, upload, and launch.

Dataset uploads create immutable revisions and normally promote the new revision to `production`. Re-uploading identical files is a no-op. Select data by name, `name@revision`, artifact id, or `config_defaults.dataset_ref`; never expose storage URIs.

Preserve the full run UUID and the `View in UI:` link printed by trigger. Use
`beaker run status <full-run-id>` for a one-shot check; exit code 3 means the
run is still active. Add `--watch` only when polling is intended. Use
`beaker run pull <full-run-id>` for results.
