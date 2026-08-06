# CLI and hosted operations

## Authentication and agent selection

- `beaker auth status` checks the user-level login; `beaker login` creates it.
- `beaker login --agent --agent-name "<Agent Name>" --repo <owner/name>` selects or creates the optimization target and writes `BEAKER_API_BASE_URL`, `BEAKER_API_KEY`, and `BEAKER_AGENT_KEY` to `.beaker/.env`.
- Selection precedence is explicit `--agent`/`--agent-key`, then `BEAKER_AGENT_KEY`, then `agent_key` in `.beaker/beaker.yaml`.
- Agents represent optimization targets, not repositories. Agent setup discovers the selected YAML and stores it on the agent as `beaker_config_path`, relative to the Git root. Rerunning agent login synchronizes this value for an existing agent.
- Archived agents retain history and released prompt serving but reject new changes. Their keys cannot be reused; choose a different target name.

Do not ask the developer to paste API keys when CLI login is available. `BEAKER_AGENT_KEY` is an agent selector, not a credential-bound API key.

## Config location and monorepos

The default config is `.beaker/beaker.yaml` under the selected project root.
Enter that root first, then use the same config selection for every command:

```bash
cd services/invoices
beaker init
beaker login --agent --agent-name "Invoice Extraction" --repo acme/invoices

# Or choose another location inside this project:
beaker --config-file config/beaker.yaml init
beaker --config-file config/beaker.yaml login --agent --agent-name "Invoice Extraction" --repo acme/invoices
```

`BEAKER_CONFIG_FILE` is equivalent to `--config-file`. The CLI converts the
discovered location to a Git-root-relative `beaker_config_path`, such as
`services/invoices/.beaker/beaker.yaml`, when creating or selecting the agent.
If a later command runs from the Git root, pass that full repository-relative
path as its selector. Paths must remain inside the Git repository. Login writes
`.beaker/.env` under its working directory, so run it from the intended project
root when credentials should live beside that project's config.

## Hosted environment variables

Repository-local environment values do not become hosted runtime secrets. Manage required provider or application variables explicitly:

```bash
beaker agent env list --agent <agent-key>
printf '%s' "$OPENAI_API_KEY" | beaker agent env set OPENAI_API_KEY --value-stdin --agent <agent-key>
beaker agent env delete OPENAI_API_KEY --agent <agent-key>
```

Beaker lists names and hints only and does not return plaintext values. Never log or commit secret values.

## Hosted build, data, and run ordering

1. Ensure the target agent exists and has repository access.
2. Before the first dataset upload, build a READY spec when necessary:

   ```bash
   beaker spec build-from-github --ref <branch>
   ```

3. Upload and inspect the dataset:

   ```bash
   beaker dataset upload <dataset-dir> --name <dataset-name> --total-count <n> --split train=<n> --split val=<n> --agent <agent-key>
   beaker dataset list --agent <agent-key>
   beaker dataset show <dataset-name> --agent <agent-key>
   ```

4. Trigger only with explicit developer authorization:

   ```bash
   beaker run trigger --ref <branch> --dataset <dataset-name>
   ```

Both build and trigger default to `.beaker/beaker.yaml`. Run them from the same
project root used for setup, or carry the same `--config-file` or
`BEAKER_CONFIG_FILE` selection through. The stored `beaker_config_path` lets
hosted operations resolve the same nested YAML.

Dataset uploads create immutable revisions and normally promote the new revision to `production`. Re-uploading identical files is a no-op. Select data by name, `name@revision`, artifact id, or `config_defaults.dataset_ref`; never expose storage URIs.

Preserve the full run UUID and the `View in UI:` link printed by trigger. Use `beaker run status <full-run-id> --once` for a one-shot check; exit code 3 means the run is still active. Use `beaker run pull <full-run-id>` for results.
