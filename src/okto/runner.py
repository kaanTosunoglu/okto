import json
import shlex
import subprocess
import sys
import re
from pathlib import Path

CONFIG_PATH = Path(".okto/config.json")
AGENTS_MD_PATH = Path(".okto/agents.md")

# {prompt}, '{prompt}' or "{prompt}" in a command_format.
_PROMPT_PLACEHOLDER = re.compile(r"""(['"]?)\{prompt\}\1""")

def _build_command(cmd_format: str, prompt: str) -> str:
    """Substitutes the prompt into cmd_format as one shell-quoted argument.

    Quotes written around the placeholder in agents.md are replaced by
    shlex.quote, so the prompt reaches the agent literally whichever quote
    style the format uses. The placeholder must be a whole argument, not part
    of a larger quoted string.
    """
    quoted = shlex.quote(prompt)
    return _PROMPT_PLACEHOLDER.sub(lambda _: quoted, cmd_format)

def _get_agent_command(agent_name: str) -> str:
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found.")
        sys.exit(1)
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    agent_cfg = config.get("agents", {}).get(agent_name)
    if not agent_cfg:
        print(f"Error: Agent '{agent_name}' not found in configuration.")
        sys.exit(1)
    
    return agent_cfg.get("command", agent_name)

def _get_command_format(agent_name: str) -> str:
    """Parses agents.md to find command_format for the given agent."""
    if not AGENTS_MD_PATH.exists():
        return ""
    
    content = AGENTS_MD_PATH.read_text(encoding="utf-8")
    # Search for agent section and command_format field
    # We use a more precise regex to find the specific agent section
    pattern = rf"## {agent_name}(.*?)(?:\n##|\Z)"
    agent_section_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if agent_section_match:
        section_content = agent_section_match.group(1)
        format_match = re.search(r"command_format:\s*(.*?)(?:\n|$)", section_content)
        if format_match:
            return format_match.group(1).strip()
    return ""

# Headings writer.py puts in <agent>_active.md. Section bodies can contain other "## " lines
# (architecture.md entries in Relevant Context), so a section ends only at one of these headings.
_TASK_FILE_SECTIONS = ("Active Task", "Relevant Context", "Files", "Completion Criteria", "Status")
# Sections sent to the agent as its prompt. Completion Criteria and Status are for okto and the user.
_PROMPT_SECTIONS = ("Active Task", "Relevant Context", "Files")

def _read_task_file(agent_name: str) -> str:
    file_path = Path(f".okto/{agent_name}_active.md")
    return file_path.read_text(encoding="utf-8") if file_path.exists() else ""

def _get_section(content: str, name: str) -> str:
    """Returns the stripped body of a "## <name>" section of a task file."""
    headings = "|".join(re.escape(s) for s in _TASK_FILE_SECTIONS)
    pattern = rf"^## {re.escape(name)}\n(.*?)(?=^## (?:{headings})$|\Z)"
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    return match.group(1).strip() if match else ""

def _get_agent_prompt(agent_name: str) -> str:
    """Builds the agent's prompt from the non-empty prompt sections of its task file."""
    content = _read_task_file(agent_name)
    parts = []
    for name in _PROMPT_SECTIONS:
        body = _get_section(content, name)
        if body:
            parts.append(f"## {name}\n{body}")
    return "\n\n".join(parts)

def _parse_verify_command(agent_name: str) -> str:
    content = _read_task_file(agent_name)
    if not content:
        print(f"Warning: .okto/{agent_name}_active.md not found. Skipping verification.")
        return ""
    # Only look in Completion Criteria, so a <verify> tag quoted in the project history is never run.
    match = re.search(r"<verify>(.*?)</verify>", _get_section(content, "Completion Criteria"), re.DOTALL)
    return match.group(1).strip() if match else ""

def run(task: dict) -> bool:
    agent = task.get("agent", "unknown").lower()
    active_file = f".okto/{agent}_active.md"
    agent_cmd = _get_agent_command(agent)
    
    cmd_format = _get_command_format(agent)
    if cmd_format:
        prompt = _get_agent_prompt(agent)
        full_cmd = _build_command(cmd_format, prompt)
        # The prompt carries the whole project history, so show its size instead of its text.
        shown_cmd = _build_command(cmd_format, f"<{len(prompt)}-character prompt from {active_file}>")
    else:
        full_cmd = shown_cmd = f"{agent_cmd} {active_file}"
        
    print(f"\nExecuting: {shown_cmd}")
    print("-" * 50)
    
    try:
        # Run the agent command
        result = subprocess.run(full_cmd, shell=True)
        print("-" * 50)
        print(f"Agent finished with exit code: {result.returncode}")
        
        if result.returncode != 0:
            print(f"Error: Agent {agent} failed.")
            return False
            
        # Parse and run verify command
        verify_cmd = _parse_verify_command(agent)
        if verify_cmd:
            print(f"Running verification: {verify_cmd}")
            v_result = subprocess.run(verify_cmd, shell=True)
            if v_result.returncode == 0:
                print("Verification PASSED.")
                return True
            else:
                print("Verification FAILED.")
                return False
        else:
            print("No verification command found. Skipping.")
            return True
            
    except Exception as e:
        print(f"An error occurred during execution: {e}")
        return False

if __name__ == "__main__":
    # Simple isolation test
    print("Testing runner in isolation...")
    
    # We need a .okto/config.json and an active file for this to work
    Path(".okto").mkdir(exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({
            "orchestrator": {"provider": "ollama", "model": "qwen3:8b"},
            "agents": {
                "test-agent": {"enabled": True, "command": "echo 'Hello from test-agent'"},
                "format-agent": {"enabled": True, "command": "echo"}
            }
        }, f, indent=4)
        
    AGENTS_MD_PATH.write_text("""## test-agent
role: tester
notes:

## format-agent
role: formatter
command_format: echo "The task is: {prompt}"
notes:
""", encoding="utf-8")

    active_file_path = Path(".okto/test-agent_active.md")
    active_file_path.write_text("""## Active Task
Test task

## Completion Criteria
<done>Test done</done>
<verify>echo 'Verifying...' && true</verify>
""", encoding="utf-8")

    format_active_file = Path(".okto/format-agent_active.md")
    format_active_file.write_text("""## Active Task
Format this task

## Completion Criteria
<done>Format done</done>
<verify></verify>
""", encoding="utf-8")

    print("\n--- Testing default behavior ---")
    run({"agent": "test-agent", "task": "Test task"})
    
    print("\n--- Testing command_format behavior ---")
    run({"agent": "format-agent", "task": "Format this task"})
