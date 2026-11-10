# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`okto` is an interactive CLI orchestrator. A local Ollama model breaks a user request into steps and routes each step to an external coding-agent CLI (`claude`, `codex`, `gemini`, `qwen`, `copilot`). A human approves the plan, each result, and each update to the knowledge files. Over time okto records per-agent notes and scores and uses them to route future tasks.

## Commands

```bash
# Setup (Python >=3.12). requirements.txt pins the exact versions.
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .

# Run: start it from the project you want to orchestrate (all state goes in ./.okto/)
okto                     # or: python -m okto.main
```

You need a running Ollama with the configured model pulled (`ollama pull <model>`). The agent CLIs must be on PATH.

The repo has no test suite, linter, or formatter. Each module has an `if __name__ == "__main__":` smoke test (`python src/okto/<module>.py`). Some of them need Ollama and some are interactive. **They read and write `./.okto/` in the current directory**:
- `runner.py` always overwrites `.okto/config.json` and `.okto/agents.md`
- `updater.py` overwrites `agents.md` and `claude_active.md`
- `writer.py` overwrites `claude_active.md` and `codex_active.md`

Run them from a scratch directory, not from the repo root or a real project.

## Architecture

**Control flow** (`main.start_command` REPL):
`planner.plan` → for each task: `writer.write_active_files` → `runner.run` → `approver.approve` → `updater.update`

- The planner sends one prompt to Ollama and expects `{"tasks": [{step, task, agent, reason}]}`. The user answers y/n/revise. Choosing revise re-prompts with the notes added.
- Per task, the approver returns `"next"`, `"retry"` (max 3), `"skip"`, or `("revise", notes)`. Revise appends `REVISION NOTES:` to the task text and reruns. `updater.update` runs on accept and when retries run out, not on skip.
- `planner`, `runner` and `ollama_client` call `sys.exit` on errors. Inside the REPL that ends the whole program. For example, rejecting a plan with `n` quits okto.

**State.** All state lives in `./.okto/`, relative to the cwd (gitignored). Each module hardcodes its own `Path(".okto/...")`; there is no shared config module.
- `config.json`: holds `orchestrator.{provider, model, think}` and `agents.<name>.{enabled, command}`. Written by `/init` (`main.init_command`).
- `agents.md`: per-agent profile, also written by `/init`.
- `<agent>_active.md`: the current task file for that agent, overwritten on every task. Sections: `## Active Task`, `## Relevant Context`, `## Completion Criteria` (`<done>`, `<verify>`), `## Status`.
- `architecture.md`: an append-only project history log. Its full contents are injected as "Relevant Context" into every active file, and from there into the agent's prompt.

**`agents.md` is a load-bearing text format**, parsed with regexes in three places: `planner._get_agent_details`, `runner._get_command_format`, and `updater._update_scores` / `_update_agents`. The expected shape:
```
## <agent>
role: ...            # role/strong/weak/command_format are single-line
strong: ...
weak: ...
command_format: ...  # contains {prompt}
notes:
- free-form lines appended by updater
scores:
  code: 0.5          # categories: code, analysis, file_ops, planning
  analysis: 0.5
  ...
```
If you change this layout, update all three parsers and the generator in `main.init_command`.

**Agent invocation** (`runner.run`):
- If the agent has a `command_format`, the prompt is made of the non-empty `Active Task`, `Relevant Context` and `Files` sections of its active file (`runner._get_agent_prompt`). `runner._build_command` puts the prompt in place of `{prompt}` through `shlex.quote`, and the command runs with `shell=True`. Quotes around the placeholder (`'{prompt}'` or `"{prompt}"`) are dropped and replaced, so either style works. The placeholder must be a whole argument, not part of a larger quoted string.
- `runner._get_section` ends a section only at one of the headings that `writer.py` writes (`_TASK_FILE_SECTIONS`). This matters because Relevant Context contains `## ` lines from `architecture.md`. If you change the task-file template, change that tuple too.
- The `command` from `config.json` is only a fallback when there is no `command_format`. It runs as `<command> .okto/<agent>_active.md`.
- After a zero exit code, the contents of `<verify>…</verify>` in the Completion Criteria section run as a shell command to decide success. The writer always emits an empty `<verify>`, so this check is normally skipped.

**Learning loop** (`updater.update`). After each accepted task it makes three Ollama calls, all with `think=False`:
1. A one-line summary appended to `architecture.md` (user confirms).
2. A short agent note appended under `notes:` (user confirms).
3. A task category, used to update that agent's score as an EMA: `new = 0.8*old + 0.2*s`. On success `s` is 1.0, 0.7 or 0.5 for 0, 1 or 2+ retries. On failure `s` is 0.2.

**Ollama** (`ollama_client.ask`) always returns parsed JSON. With `think=True` it omits `format="json"` (needed for thinking models), so the prompt itself must get the model to return JSON. Only the planner uses the `think` setting from config. If `ollama.show` reports the model without the `thinking` capability, `ask` prints a note once and falls back to `think=False` with `format="json"`. `DEFAULT_MODEL` (`qwen3:8b`) is also the default model in `/init`.

## Conventions

- Modules import siblings with `try: from okto import x` / `except ImportError: import x`. Keep this pattern so `python src/okto/x.py` still works.
- Adding a new agent CLI means changing `main.init_command` in three places: `available_agents`, the `agent_details` dict (role/strong/weak/command_format), and the user-facing strings that list agent names. Commit `3d7e3ee` is an example. Existing `.okto/` directories only pick up a new agent after `/init` or a hand edit.
- Add new dependencies to both `pyproject.toml` and `requirements.txt`.
- UI: `main.py` uses a `rich` Console plus a `prompt_toolkit` `PromptSession` (purple palette `#c8a8e8` / `#6b3a9a`). The other modules use plain `print`/`input`.
