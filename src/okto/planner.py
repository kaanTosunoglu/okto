import json
import sys
import re
from pathlib import Path
try:
    from okto import ollama_client
except ImportError:
    # If not running from the root as a package
    import ollama_client

CONFIG_PATH = Path(".okto/config.json")
AGENTS_MD_PATH = Path(".okto/agents.md")

def _get_enabled_agents():
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found. Please run 'okto init' first.")
        sys.exit(1)
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    agents = config.get("agents", {})
    enabled_agents = [name for name, cfg in agents.items() if cfg.get("enabled", False)]
    return enabled_agents

def _get_agent_details(enabled_agents):
    """Parses agents.md for details of enabled agents."""
    if not AGENTS_MD_PATH.exists():
        return {agent: {} for agent in enabled_agents}
    
    content = AGENTS_MD_PATH.read_text(encoding="utf-8")
    details = {}
    
    for agent in enabled_agents:
        agent_details = {}
        # Find agent section
        pattern = rf"## {agent}(.*?)(?:\n##|\Z)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            section = match.group(1)
            # Standard fields (single line)
            for field in ["role", "strong", "weak", "command_format"]:
                field_match = re.search(rf"{field}:\s*(.*?)(?:\n|$)", section, re.IGNORECASE)
                if field_match:
                    agent_details[field] = field_match.group(1).strip()
            
            # Notes field (can be multi-line)
            notes_match = re.search(rf"notes:\s*(.*?)(?:\n[a-z_]+:|\Z)", section, re.DOTALL | re.IGNORECASE)
            if notes_match:
                agent_details["notes"] = notes_match.group(1).strip()

            # Scores field
            scores_match = re.search(rf"scores:\s*(.*?)(?:\n[a-z_]+:|\Z)", section, re.DOTALL | re.IGNORECASE)
            if scores_match:
                scores_text = scores_match.group(1).strip()
                scores = {}
                for line in scores_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        try:
                            scores[k.strip()] = float(v.strip())
                        except ValueError:
                            pass
                agent_details["scores"] = scores
                
        details[agent] = agent_details
    return details

def _display_plan(plan):
    print("\nProposed Plan:")
    print("-" * 50)
    for task in plan:
        print(f"Step {task['step']}: [{task['agent'].upper()}] - {task['task']}")
        print(f"   Reason: {task['reason']}")
    print("-" * 50)

def plan(user_prompt: str) -> list:
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found. Please run 'okto init' first.")
        sys.exit(1)
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    think_value = config.get("orchestrator", {}).get("think", True)
    enabled_agents = [name for name, cfg in config.get("agents", {}).items() if cfg.get("enabled", False)]
    agent_details = _get_agent_details(enabled_agents)
    
    available_agents_lines = []
    for agent, details in agent_details.items():
        line = f"- {agent}:"
        if "role" in details: line += f"\n  Role: {details['role']}"
        if "strong" in details: line += f"\n  Strong: {details['strong']}"
        if "weak" in details: line += f"\n  Weak: {details['weak']}"
        if "command_format" in details: line += f"\n  Format: {details['command_format']}"
        if "notes" in details and details["notes"]: line += f"\n  Notes: {details['notes']}"
        if "scores" in details and details["scores"]:
            scores_str = ", ".join([f"{k}={v}" for k, v in details["scores"].items()])
            line += f"\n  Scores: {scores_str}"
        available_agents_lines.append(line)
    
    available_agents_str = "\n".join(available_agents_lines)

    system_prompt = f"""You are Okto, a task planner. Break the user's task into sequential steps.
Available agents and their specific characteristics:
{available_agents_str}

Routing guidelines:
- Choose the agent whose 'Strong' traits match the task requirements.
- Avoid agents whose 'Weak' traits conflict with the task.
- Use the provided 'Role' and 'Format' to understand how they operate.
- Use 'Notes' and 'Scores' to gauge past performance and specific experiences.
- The 'task' field must be specific and self-contained. It must include all concrete details from the user's prompt (names, values, exact strings, filenames). Never use vague descriptions like 'write the program' or 'perform the task'. Bad example: 'Write the hello world program in the desired format'. Good example: 'Write a Python script that prints exactly: Hello world from KAAN'.

Return a JSON object with a "tasks" list.
Each task must have: "step" (integer), "task" (string), "agent" (string), "reason" (string).

Example:
{{
  "tasks": [
    {{
      "step": 1,
      "task": "Write a Python script named 'hello.py' that prints exactly: Hello world from KAAN",
      "agent": "codex",
      "reason": "Codex is best for code writing and this task requires specific code implementation"
    }}
  ]
}}
"""

    current_prompt = user_prompt
    while True:
        max_retries = 3
        tasks = None
        
        for attempt in range(max_retries):
            try:
                full_prompt = f"System: {system_prompt}\nUser Prompt: {current_prompt}"
                response = ollama_client.ask(full_prompt, think=think_value)
                
                if isinstance(response, dict) and "tasks" in response:
                    tasks = response["tasks"]
                    if isinstance(tasks, list) and len(tasks) > 0:
                        break
                
                print(f"Attempt {attempt + 1}/{max_retries}: Invalid response format. Retrying...")
            except Exception as e:
                print(f"Attempt {attempt + 1}/{max_retries}: Error: {e}")
        
        if not tasks:
            print("Error: Failed to generate a valid plan after 3 attempts. Exiting.")
            sys.exit(1)
            
        _display_plan(tasks)
        
        choice = input("Approve this plan? (y/n/revise): ").strip().lower()
        
        if choice == 'y':
            return tasks
        elif choice == 'n':
            print("Operation cancelled.")
            sys.exit(0)
        elif choice == 'revise':
            revision_notes = input("Enter revision notes: ").strip()
            current_prompt = f"Previous Prompt: {current_prompt}\nUser Revision Notes: {revision_notes}\nRefine the plan based on these notes."
        else:
            print("Invalid choice. Please enter 'y', 'n', or 'revise'.")

if __name__ == "__main__":
    # Simple isolation test
    print("Testing planner in isolation...")
    # We need a .okto/config.json and agents.md for this to work
    if not CONFIG_PATH.exists():
        print("Creating a temporary .okto/config.json for testing...")
        Path(".okto").mkdir(exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "orchestrator": {"provider": "ollama", "model": ollama_client.DEFAULT_MODEL},
                "agents": {
                    "claude": {"enabled": True, "command": "claude"},
                    "codex": {"enabled": True, "command": "codex"},
                    "gemini": {"enabled": True, "command": "gemini"}
                }
            }, f, indent=4)
    
    if not AGENTS_MD_PATH.exists():
        print("Creating a temporary .okto/agents.md for testing...")
        AGENTS_MD_PATH.write_text("""## claude
role: architect / analyst
strong: complex analysis, architecture
weak: long files
command_format: claude {prompt}

## codex
role: developer
strong: code writing, refactoring
weak: architecture decisions
command_format: codex {prompt}

## gemini
role: reader / processor
strong: long context
weak: decisive tasks
command_format: gemini {prompt}
""", encoding="utf-8")

    test_prompt = "Refactor the existing code and write a comprehensive analysis of the system architecture."
    final_plan = plan(test_prompt)
    print("\nFinal approved plan:")
    print(final_plan)
