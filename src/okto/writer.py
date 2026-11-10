import os
from pathlib import Path

def write_active_files(tasks: list, context: str = "") -> None:
    """
    Writes *_active.md files for each task in the approved task list.
    Naming convention: {agent_name}_active.md
    """
    okto_dir = Path(".okto")
    # Ensure .okto directory exists
    okto_dir.mkdir(exist_ok=True)

    for task_info in tasks:
        agent = task_info.get("agent", "unknown").lower()
        description = task_info.get("task", "")
        
        filename = f"{agent}_active.md"
        file_path = okto_dir / filename
        
        content = f"""## Active Task
{description}

## Relevant Context
{context if context else ""}

## Files


## Completion Criteria
<done>{description}</done>
<verify></verify>

## Status
[ ] pending approval
[ ] approved
[ ] revision requested → 
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Created {file_path}")

if __name__ == "__main__":
    # Simple isolation test
    print("Testing writer in isolation...")
    sample_tasks = [
        {"step": 1, "task": "Analyze the codebase", "agent": "claude", "reason": "Claude is good at analysis"},
        {"step": 2, "task": "Implement the feature", "agent": "codex", "reason": "Codex is good at implementation"}
    ]
    write_active_files(sample_tasks, "Existing codebase is in Python.")
    
    # Verify files
    for task in sample_tasks:
        p = Path(f".okto/{task['agent']}_active.md")
        if p.exists():
            print(f"Verification: {p} exists.")
            # Optional: print content
            # print(p.read_text())
        else:
            print(f"Verification FAILED: {p} does not exist.")
