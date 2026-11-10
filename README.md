# 🐙 okto

okto is a command-line orchestrator for AI coding agents. You give it a task. A local LLM running in [Ollama](https://ollama.com) splits the task into steps and assigns each step to the agent CLI that fits it best: Claude Code, Codex, Gemini CLI, Qwen Code or GitHub Copilot CLI. You approve the plan before any agent starts and approve each result before okto moves on.

Over time okto keeps notes and scores for each agent in your project and uses them to route later tasks.

> **Status:** early (0.1.0). It works end to end but has no test suite yet, and the interface may change.

## How it works

```
you → prompt
  ↓
okto (local LLM via Ollama) → splits the task into steps and picks an agent for each
  ↓  you approve the plan
agent CLI (claude / codex / gemini / qwen / copilot) → does the work
  ↓  you approve the result
okto → updates the project history and the agent's notes and score
```

- **Files are the only bridge.** Agents never talk to each other or to okto directly. Before each step, okto writes the task and its context to `.okto/<agent>_active.md`, then starts the agent CLI with that task and context as its prompt.
- **Two approval points.** No agent starts until you approve the plan. okto doesn't move to the next step until you approve the result. Changes to the history and the agent notes are also shown to you before they are written.
- **Sequential and blocking.** okto runs one agent at a time and waits for it to exit.
- **Routing improves with use.** Each agent has a score in four task categories (code, analysis, file ops, planning), and the planner sees these scores and the agent's notes when it assigns steps.

## Requirements

- macOS or Linux. okto passes prompts to agents through a POSIX shell.
- Python 3.12 or newer.
- [Ollama](https://ollama.com), running, with at least one model pulled. The default model is `qwen3:8b`; get it with `ollama pull qwen3:8b`.
- At least one supported agent CLI, installed, signed in, and on your `PATH`.

## Installation

```bash
git clone https://github.com/kaanTosunoglu/okto.git
cd okto
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `okto` command. `requirements.txt` pins exact versions if you need a reproducible environment.

## Usage

okto works on the current directory, so start it from the root of the project you want to change:

```bash
cd ~/code/my-project
okto
```

On the first run okto offers to set up the project. It asks four things:
1. The Ollama model to use (default `qwen3:8b`).
2. Whether to turn on thinking mode (default yes). If the model you chose doesn't support thinking, okto detects that and plans without it.
3. Which agents to enable. Leave it blank to enable all of them.
4. The command name for each enabled agent.

It saves your answers in `.okto/config.json` and `.okto/agents.md`.

Then type a task at the `🐙 >` prompt. The bottom toolbar shows the current model and the enabled agents.

| Prompt | Answers |
|---|---|
| Approve this plan? | `y` runs the plan. `n` cancels and exits okto. `revise` asks for notes and makes a new plan. |
| Result looks good? (agent succeeded) | `y` accepts the result and moves to the next step. `n` skips this step. `revise` asks for notes and reruns the step with them. |
| Retry this task? (agent failed) | `y` runs it again, up to 3 attempts in total. `n` skips the step. |
| Append to architecture.md? / Add note to agents.md? | Shown after you accept a result. Each is `y` or `n`. |

In-session commands:
- `/init` reconfigures the project.
- `/quit` exits okto.
- `Esc` clears the current line, and `Ctrl+C` cancels it.

> [!WARNING]
> The default agent commands run in non-interactive, auto-approve modes: Codex uses `--full-auto`, Gemini and Qwen use `-y`. In those modes an agent can edit files and run commands in your project without asking. Use okto on code that's under version control, and review each result before you accept it.

## The `.okto/` directory

Each project you use okto in gets a `.okto/` directory. It is per-user state, so you'll usually want it in that project's `.gitignore`.

| File | Contents |
|---|---|
| `config.json` | The Ollama model, the thinking setting, and which agents are enabled with which command. |
| `agents.md` | One profile per agent: its role, strengths, weaknesses, `command_format`, notes and scores. |
| `<agent>_active.md` | The step that agent is working on now. Rewritten before every run. |
| `architecture.md` | A log of completed tasks, one line each, appended only after you approve. okto copies it into each task file, so every agent gets it as context. |

Running `/init` again rewrites `agents.md` from scratch, which **resets that project's agent notes and scores**.

### `agents.md`

```markdown
## codex
role: pragmatic software engineer / coding agent
strong: precise code changes, debugging, test-driven fixes
weak: speculative product strategy
command_format: codex exec --full-auto "{prompt}"
notes:
- handled the auth refactor cleanly

scores:
  code: 0.5
  analysis: 0.5
  file_ops: 0.5
  planning: 0.5
```

You can edit these profiles by hand. okto reads the file with simple patterns, so a few rules matter:
- Each agent's section starts with `## <name>`.
- `role`, `strong`, `weak` and `command_format` each stay on one line.
- `notes:` and `scores:` stay at the end of the section.

**`command_format`** is the shell command that starts the agent. okto replaces `{prompt}` with the agent's prompt, quoted safely for the shell. The prompt is built from the agent's [task file](#task-files). You can write the placeholder as `{prompt}`, `'{prompt}'` or `"{prompt}"`; all three behave the same. It has to be a separate argument, though, not part of a longer quoted string.

If an agent has no `command_format`, okto runs `<command> .okto/<agent>_active.md` instead, where `<command>` is the agent's command from `config.json`.

These are the default formats that `/init` writes:

| Agent | `command_format` | Notes |
|---|---|---|
| claude | `claude "{prompt}"` | Opens an interactive Claude Code session. Exit it to return to okto. |
| codex | `codex exec --full-auto "{prompt}"` | |
| gemini | `gemini -p "{prompt}" -y` | |
| qwen | `qwen -p '{prompt}' -y` | |
| copilot | `copilot -p '{prompt}'` | |

**Adding another CLI** takes no code changes:
1. Add an entry under `agents` in `config.json` with `"enabled": true`.
2. Add a matching `## <name>` section to `agents.md`.

**Scores** start at 0.5 in each category. After a task, okto asks the model which category the task belongs to and updates that score to `0.8 × old + 0.2 × result`. The result is 1.0 if the task succeeded on the first try, 0.7 after one retry, and 0.5 after more. It is 0.2 if the task failed.

### Task files

Each `<agent>_active.md` has the following sections:

```markdown
## Active Task
## Relevant Context
## Files
## Completion Criteria
<done>human-readable success condition</done>
<verify>shell command that checks the result</verify>
## Status
```

The agent's prompt is made of the non-empty Active Task, Relevant Context and Files sections. Completion Criteria and Status are only for okto and for you.

If the `<verify>` tag under Completion Criteria contains a command, okto runs it after the agent exits with code 0, and the command decides whether the step succeeded. okto doesn't fill `<verify>` yet. For now, a step succeeds when the agent exits with code 0.

## Development

```bash
source .venv/bin/activate
pip install -e .
```

| Module | Role |
|---|---|
| `main.py` | Entry point (`okto`), the interactive prompt loop, and `/init`. |
| `planner.py` | Asks Ollama for the plan and handles plan approval. |
| `writer.py` | Writes the `<agent>_active.md` task files. |
| `runner.py` | Runs the agent CLI and the `<verify>` check. |
| `approver.py` | Asks you to approve, revise, retry or skip a result. |
| `updater.py` | Updates `architecture.md` and the agent notes and scores. |
| `ollama_client.py` | Thin wrapper around the Ollama SDK that returns parsed JSON. |

Each module can be run alone for a quick check, for example `python src/okto/writer.py`. These checks read and overwrite files in `./.okto/` in the current directory, so run them from an empty scratch directory.

Conventions:
- Follow PEP 8.
- Add new dependencies to both `pyproject.toml` and `requirements.txt`.

## Not supported yet

- Running steps in parallel
- Automatic evaluation of results
- Live view of agent output inside okto
- A web interface
- Multiple users
- Windows

## License

[MIT](LICENSE)
