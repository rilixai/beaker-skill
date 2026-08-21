# Beaker Skills

Portable agent guidance for setting up and operating
[Beaker](https://pypi.org/project/beaker-sdk/) optimization runs in a Python
repository, with explicit support for existing logical-target specs.

The canonical Agent Skills are:

- [`beaker-setup`](skills/beaker-setup), for connecting and validating a
  repository; and
- [`beaker-usage`](skills/beaker-usage), for launching, monitoring, pulling,
  and cancelling hosted runs.

Claude and Codex marketplace metadata point to these same folders; there are no
platform-specific copies.

## Install

Install globally for all detected agents (non-interactive):

```bash
npx skills add rilixai/beaker-skill --skill beaker-setup --global --yes
npx skills add rilixai/beaker-skill --skill beaker-usage --global --yes
```

The `skills` CLI detects the agents installed on your machine. `--yes` accepts
those detected agents without opening the agent-selection menu, and `--global`
makes the skill available across projects.

> [!NOTE]
> **Known issue (as of 2026-08-20):** with `--global --yes`, the `skills` CLI may report
> `Failed to install 1 ... PromptScript: PromptScript does not support global
> skill installation`. This is harmless and can be ignored: the skill still
> installs globally for every other detected agent, and PromptScript reads
> project-local `.agents/skills` anyway. It is a `skills` CLI bug tracked
> upstream at
> [vercel-labs/skills#1352](https://github.com/vercel-labs/skills/issues/1352).

Install globally for a specific agent:

```bash
npx skills add rilixai/beaker-skill --skill beaker-setup --agent cursor --global --yes
npx skills add rilixai/beaker-skill --skill beaker-setup --agent devin --global --yes
```

GitHub CLI 2.90 or newer:

```bash
gh skill install rilixai/beaker-skill beaker-setup
gh skill install rilixai/beaker-skill beaker-usage
```

Claude Code:

```text
/plugin marketplace add rilixai/beaker-skill
/plugin install beaker@beaker
```

Codex:

```text
codex plugin marketplace add https://github.com/rilixai/beaker-skill
codex plugin add beaker@beaker
```

After installation, ask your agent to "set up Beaker in this repository" or
"launch a Beaker optimization run." The setup skill can bootstrap the CLI with
`uvx --from beaker-sdk beaker init`; installing either skill does not require
Python or Beaker.

## Update

Use your marketplace's update flow or:

```bash
npx skills update beaker-setup
npx skills update beaker-usage
```

The canonical version is stored in [`VERSION`](VERSION). When releasing a new
version, update that file and run:

```bash
python3 scripts/sync_version.py
```

The repository checks fail if either marketplace manifest drifts from
`VERSION`.

## Development

Run the repository checks with:

```bash
python3 -m unittest discover -s tests
```

The skill is MIT licensed. Review agent instructions before installation just as you would review executable tooling.
