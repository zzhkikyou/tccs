# tccs — Tiny Claude Code Switch

> One-command profile switching for LLM provider environment variables.

![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![No dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

**tccs** (Tiny Claude Code Switch) is a single-file Python CLI that lets you manage multiple LLM provider profiles and switch between them instantly. Each profile is a JSON file of environment variables; activating a profile updates a symlink and exports the variables into your current shell.

## Table of Contents

- [Why tccs?](#why-tccs)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
- [Usage Examples](#usage-examples)
- [How It Works](#how-it-works)
- [Claude Code Integration Notes](#claude-code-integration-notes)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Why tccs?

- **Single-file, stdlib-only Python 3 script** — no packages to install.
- **Profile isolation** — keep each provider's keys, model names, and settings in its own JSON file.
- **Instant switching** — `tccs-switch <profile>` applies the new env vars in the current shell.
- **Claude Code aware** — optionally clears the `env` block in Claude Code's `settings.json` so shell variables remain the source of truth.

## Installation

```bash
# Clone the repository
git clone git@gitee.com:zzhkikyou/tccs.git
cd tccs

# Make it executable
chmod +x tccs

# Optional: add to your PATH
mkdir -p ~/.local/bin
ln -s "$(pwd)/tccs" ~/.local/bin/tccs
```

Requirements: **Python 3.6+**, no third-party dependencies.

## Quick Start

**1. Run the setup wizard**

```bash
./tccs
```

This injects `tccs-switch` and `tccs-refresh` shell functions into your shell config file (`.bashrc`, `.bash_profile`, or `.zshrc`). It also creates an example profile under `~/.tccs/`.

**2. Add your first profile**

```bash
./tccs -a
```

You will be prompted for a profile name and `$EDITOR` will open a template. Fill in real values, save, and exit.

Alternatively, create a profile manually:

```bash
cp ~/.tccs/llm_example.json ~/.tccs/llm_anthropic.json
# edit ~/.tccs/llm_anthropic.json with your real keys
```

Example profile (`~/.tccs/llm_anthropic.json`):

```json
{
  "ANTHROPIC_API_KEY": "sk-ant-xxx",
  "ANTHROPIC_MODEL": "claude-sonnet-4-20250514",
  "ANTHROPIC_BASE_URL": "https://api.anthropic.com"
}
```

**3. Switch profiles**

```bash
tccs-switch anthropic
```

Or, without the shell helper:

```bash
eval "$(./tccs -w anthropic)"
```

## Command Reference

### CLI commands

| Command | Description |
|---------|-------------|
| `./tccs` | Run the interactive setup wizard |
| `./tccs -r` | Re-run setup (update shell integration) |
| `./tccs -s`, `--show` | List all profiles |
| `./tccs -l` | Show the active profile and its environment variables |
| `./tccs -w <name>` | Switch to profile `name` and print `export` statements |
| `./tccs -a`, `--add` | Add a new profile interactively |
| `./tccs -e [<name>]`, `--edit [<name>]` | Edit a profile interactively |
| `./tccs -d <name>` | Delete a profile |

### Shell helpers

After setup, these functions are available in every new shell:

| Function | Description |
|----------|-------------|
| `tccs-switch <name>` | Switch to profile `name` and apply env vars in the current shell |
| `tccs-refresh` | Reload the currently active profile |

## Usage Examples

### Add and switch to an Anthropic profile

```bash
./tccs -a
# Profile name: anthropic
# Fill in ANTHROPIC_API_KEY, ANTHROPIC_MODEL, etc.

tccs-switch anthropic
```

### Switch between providers

```bash
# List available profiles
./tccs -s

# Switch to OpenAI
./tccs -w openai        # prints export statements
tccs-switch openai      # applies them in the current shell
```

### Edit the active profile and refresh

```bash
./tccs -e anthropic     # edit in $EDITOR
tccs-refresh            # reload env vars in current shell
```

### Delete a profile

```bash
./tccs -d old_profile
```

## How It Works

`tccs` stores each profile as a flat JSON file under `~/.tccs/`:

```
~/.tccs/
├── llm.json -> llm_anthropic.json   # symlink to the active profile
├── config.json                       # tccs preferences
├── llm_example.json                  # template profile
├── llm_anthropic.json
├── llm_openai.json
└── llm_gemini.json
```

Each profile contains `{"KEY": "value"}` pairs that are exported as environment variables:

```bash
export ANTHROPIC_API_KEY='sk-ant-xxx'
export ANTHROPIC_MODEL='claude-sonnet-4-20250514'
```

When you run `tccs-switch <name>`, the shell function calls:

```bash
eval "$(tccs -w <name>)"
```

This updates the `~/.tccs/llm.json` symlink and evaluates the exported variables in the current shell session.

## Claude Code Integration Notes

During setup, `tccs` asks whether to **clear the `env` block in Claude Code's `settings.json` on every switch**. When enabled:

- `tccs -w <name>` sets `settings.json` `"env"` to `{}`.
- Your shell environment variables become the single source of truth for API keys and model settings.
- This avoids stale values lingering in Claude Code's own config.

You can change this later by re-running `./tccs -r` or by editing `~/.tccs/config.json`:

```json
{
  "sync_env": true
}
```

## Troubleshooting

### `tccs-switch: command not found`

The shell functions are only available after setup and in shells started **after** the config file was sourced. Run:

```bash
source ~/.bashrc   # or ~/.zshrc
```

### Profile not found

Make sure the JSON file exists as `~/.tccs/llm_<name>.json` and the name uses only letters, digits, underscores, and hyphens. List profiles with:

```bash
./tccs -s
```

### `settings.json` env is not clearing

Check that `sync_env` is enabled:

```bash
cat ~/.tccs/config.json
```

If it is `false`, re-run setup:

```bash
./tccs -r
```

## License

MIT
