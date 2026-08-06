# Beaker Setup Skill

Portable agent guidance for adding [Beaker](https://pypi.org/project/beaker-sdk/) prompt optimization to a Python repository.

The canonical Agent Skill lives at [`skills/beaker-setup`](skills/beaker-setup). Claude and Codex marketplace metadata point to that same folder; there are no platform-specific copies.

## Install

Any supported agent:

```bash
npx skills add rilixai/beaker-skill --skill beaker-setup
```

Install globally for a specific agent:

```bash
npx skills add rilixai/beaker-skill --skill beaker-setup --agent cursor --global
npx skills add rilixai/beaker-skill --skill beaker-setup --agent devin --global
```

GitHub CLI 2.90 or newer:

```bash
gh skill install rilixai/beaker-skill beaker-setup
```

Claude Code:

```text
/plugin marketplace add rilixai/beaker-skill
/plugin install beaker-setup@beaker
```

Codex:

```text
codex plugin marketplace add https://github.com/rilixai/beaker-skill
codex plugin add beaker-setup@beaker
```

After installation, ask your agent to "set up Beaker in this repository." The skill can bootstrap the CLI with `uvx --from beaker-sdk beaker init`; installing the skill itself does not require Python or Beaker.

## Update

Use your marketplace's update flow or:

```bash
npx skills update beaker-setup
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
