import os
import sys
import json
import argparse
from pathlib import Path
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings

# Global rich console
console = Console()

# Import okto modules
try:
    from okto import planner, runner, writer, approver, updater, ollama_client
except ImportError:
    # If not running from the root as a package
    import planner, runner, writer, approver, updater, ollama_client

def get_toolbar():
    """Reads config.json and returns the toolbar content."""
    okto_dir = Path(".okto")
    config_path = okto_dir / "config.json"
    if not config_path.exists():
        return "Okto (Not Initialized)"
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        model = config.get("orchestrator", {}).get("model", "unknown")
        agents = [name for name, cfg in config.get("agents", {}).items() if cfg.get("enabled")]
        return f"Model: {model} | Agents: {', '.join(agents)}"
    except:
        return "Okto (Config Error)"

def init_command():
    okto_dir = Path(".okto")
    if okto_dir.exists():
        response = console.input("[bold #c8a8e8].okto/ directory already exists. Do you want to reinitialize? (y/n): [/]").strip().lower()
        if response != 'y':
            console.print("[yellow]Operation cancelled.[/]")
            return

    # Ollama model name
    default_model = ollama_client.DEFAULT_MODEL
    model_name = console.input(f"[bold #c8a8e8]Ollama model name (default: {default_model}): [/]").strip()
    if not model_name:
        model_name = default_model

    # Enable thinking/reasoning mode
    think_input = console.input("[bold #c8a8e8]Enable thinking/reasoning mode? (y/n, default: y): [/]").strip().lower()
    think_value = think_input != 'n'

    # Which agents to enable
    console.print("\n[bold #c8a8e8]Which agents would you like to enable? (claude, codex, gemini, qwen, copilot)[/]")
    console.print("[#6b3a9a]Example: claude, gemini (leave blank for all)[/]")
    agents_input = console.input("[bold #c8a8e8]Agent selection: [/]").strip().lower()
    
    available_agents = ["claude", "codex", "gemini", "qwen", "copilot"]
    if not agents_input:
        enabled_agents_list = available_agents
    else:
        # Split by comma and clean up
        enabled_agents_list = [a.strip() for a in agents_input.replace(",", " ").split() if a.strip() in available_agents]

    if not enabled_agents_list:
        console.print("[red]No valid agents selected. Please choose claude, codex, gemini, qwen, or copilot.[/]")
        return

    # CLI command names for each agent
    agents_config = {}
    for agent in available_agents:
        is_enabled = agent in enabled_agents_list
        if is_enabled:
            cmd = console.input(f"[bold #c8a8e8]CLI command name for {agent} (default: {agent}): [/]").strip()
            if not cmd:
                cmd = agent
            agents_config[agent] = {
                "enabled": True,
                "command": cmd
            }
        else:
            agents_config[agent] = {
                "enabled": False,
                "command": agent
            }

    # Create .okto directory
    okto_dir.mkdir(exist_ok=True)

    # Write config.json
    config = {
        "orchestrator": {
            "provider": "ollama",
            "model": model_name,
            "think": think_value
        },
        "agents": agents_config
    }
    with open(okto_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    # Write agents.md
    agent_details = {
        "claude": {
            "role": "architect / analyst",
            "strong": "complex analysis, writing, architecture, short code",
            "weak": "very long files, large codebase scanning",
            "command_format": 'claude "{prompt}"'
        },
        "codex": {
            "role": "pragmatic software engineer / coding agent",
            "strong": "precise code changes, debugging, test-driven fixes, clear technical tradeoffs, pragmatic refactoring",
            "weak": "speculative product strategy, open-ended visual design taste judgments, ultra-low latency tasks",
            "command_format": 'codex exec --full-auto "{prompt}"'
        },
        "gemini": {
            "role": "full-stack architect / master analyst",
            "strong": "massive context window (2M tokens), complex architectural reasoning, cross-file analysis, multi-step planning, deep bug hunting",
            "weak": "extreme brevity, ultra-low latency tasks, legacy system nuances without documentations",
            "command_format": 'gemini -p "{prompt}" -y'
        },
        "qwen": {
            "role": "software engineering specialist",
            "strong": "iterative code development, project convention adherence, integrated tool usage (edit/search/shell), multi-step task tracking, test-driven development implementation",
            "weak": "ultra-brief responses, sub-second latency tasks, undocumented legacy system intuition, million-token context analysis",
            "command_format": "qwen -p '{prompt}' -y"
        },
        "copilot": {
            "role": "architect / interactive coding assistant",
            "strong": "fast, context-aware code generation and refactoring; clear, concise code explanations; automating repetitive coding tasks; generating tests and pull-request ready diffs; integrating with GitHub workflows",
            "weak": "lacks access to private runtime state and external services (can't run or test code here); may need guidance on repo-wide design constraints; not optimized for very large file-by-file manual scanning",
            "command_format": "copilot -p '{prompt}'"
        }
    }

    with open(okto_dir / "agents.md", "w", encoding="utf-8") as f:
        for i, agent in enumerate(enabled_agents_list):
            details = agent_details[agent]
            f.write(f"## {agent}\n")
            f.write(f"role: {details['role']}\n")
            f.write(f"strong: {details['strong']}\n")
            f.write(f"weak: {details['weak']}\n")
            f.write(f"command_format: {details['command_format']}\n")
            f.write("notes:\n")
            f.write("\n")
            f.write("scores:\n")
            f.write("  code: 0.5\n")
            f.write("  analysis: 0.5\n")
            f.write("  file_ops: 0.5\n")
            f.write("  planning: 0.5\n")
            if i < len(enabled_agents_list) - 1:
                f.write("\n")

    console.print("\n[bold #c8a8e8]🐙 okto initialized successfully! .okto/ directory and configuration files created.[/]")

def print_banner():
    content = Text(justify="center")
    
    # Header
    content.append("\n🐙  OKTO\n", style="#c8a8e8 bold")
    content.append("local cli orchestrator\n", style="#6b3a9a")
    
    # Separator
    content.append("─" * 54 + "\n", style="#2a1a4a")
    
    # Config info
    config_path = Path(".okto/config.json")
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            model = config.get("orchestrator", {}).get("model", "unknown")
            agents = [name for name, cfg in config.get("agents", {}).items() if cfg.get("enabled")]
            content.append(f"model: {model}  │  agents: {', '.join(agents)}\n", style="#6b3a9a")
        except:
            pass
            
    # Footer
    content.append("/quit to exit  •  /init to reconfigure\n", style="#2a1a4a")
    
    panel = Panel(
        content,
        width=60,
        border_style="#6b3a9a",
        style="on #0d0d14",
        padding=(0, 2)
    )
    
    console.print(panel)
    console.print("\n")

def start_command():
    print_banner()
    okto_dir = Path(".okto")
    config_path = okto_dir / "config.json"
    
    if not config_path.exists():
        response = console.input("[bold #c8a8e8]No configuration found. Would you like to initialize Okto? (y/n): [/]").strip().lower()
        if response == 'y':
            init_command()
        else:
            return

    # Setup prompt_toolkit
    session = PromptSession(history=InMemoryHistory())
    completer = WordCompleter(["/quit", "/init"], ignore_case=True)
    
    kb = KeyBindings()
    @kb.add('escape')
    def _(event):
        """Escape clears the current line."""
        event.current_buffer.text = ""

    try:
        while True:
            try:
                user_prompt = session.prompt(
                    "🐙  > ",
                    completer=completer,
                    bottom_toolbar=get_toolbar,
                    key_bindings=kb
                ).strip()
            except KeyboardInterrupt:
                # Ctrl+C cancels current input and continues
                continue
            
            if user_prompt.lower() == "/quit":
                console.print("[bold #c8a8e8]Goodbye! 🐙[/]")
                break

            if user_prompt.lower() == "/init":
                init_command()
                continue
                
            if not user_prompt:
                console.print("[yellow]Warning: Empty prompt. Please enter a task or type /quit to exit.[/]")
                continue

            # Get task plan from planner
            try:
                task_list = planner.plan(user_prompt)
            except KeyboardInterrupt:
                console.print("\n[yellow]Planning cancelled.[/]")
                continue

            if not task_list:
                console.print("[red]Failed to generate a task plan.[/]")
                continue

            # Process each task sequentially
            for task in task_list:
                max_retries = 3
                retry_count = 0
                original_desc = task.get("task", "")
                
                while retry_count < max_retries:
                    # Get context from architecture.md if it exists
                    context = ""
                    arch_file = okto_dir / "architecture.md"
                    if arch_file.exists():
                        context = arch_file.read_text(encoding="utf-8")

                    # 1. Write active file
                    writer.write_active_files([task], context=context)
                    
                    # 2. Run the agent
                    success = runner.run(task)
                    
                    # 3. Handle approval
                    choice = approver.approve(task, success)
                    
                    if choice == "next":
                        # Update knowledge and move to next task
                        updater.update(task, success=success, retry_count=retry_count)
                        break
                    elif choice == "retry":
                        retry_count += 1
                        if retry_count >= max_retries:
                            console.print(f"[red]Max retries ({max_retries}) reached for this task. Skipping.[/]")
                            updater.update(task, success=False, retry_count=retry_count)
                            break
                        console.print(f"[yellow]Retrying task (Attempt {retry_count + 1}/{max_retries})...[/]")
                        continue
                    elif choice == "skip":
                        console.print("[yellow]Skipping task.[/]")
                        break
                    elif isinstance(choice, tuple) and choice[0] == "revise":
                        notes = choice[1]
                        # Update task description for rewrite
                        task["task"] = f"{original_desc}\n\nREVISION NOTES: {notes}"
                        console.print("[cyan]Rewriting task file with revision notes and restarting...[/]")
                        continue
                    else:
                        # Fallback for "skip" or other unknown results
                        break
                        
            console.print("\n[bold #c8a8e8]🐙 All tasks completed.[/]")
    except KeyboardInterrupt:
        console.print("\n[bold #c8a8e8]Goodbye! 🐙[/]")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(prog="okto", description="Okto CLI - Local Orchestrator")
    parser.parse_args()
    start_command()

if __name__ == "__main__":
    main()
