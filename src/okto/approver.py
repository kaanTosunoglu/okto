import sys

def approve(task: dict, success: bool) -> tuple | str:
    """
    Handles the result approval loop.
    Returns: "next", "skip", "retry", or ("revise", "revision notes")
    """
    description = task.get("task", "Unknown Task")
    agent = task.get("agent", "unknown").upper()

    if not success:
        print(f"\nVerification failed for task: [{agent}] {description}")
        choice = input("Retry this task? (y/n): ").strip().lower()
        if choice == 'y':
            return "retry"
        else:
            return "skip"
    
    # success is True
    print(f"\nTask completed: [{agent}] {description}")
    print("Please review the result in the corresponding active file or workspace.")
    
    while True:
        choice = input("Result looks good? (y/n/revise): ").strip().lower()
        
        if choice == 'y':
            return "next"
        elif choice == 'n':
            return "skip"
        elif choice == 'revise':
            notes = input("Enter revision notes for the agent: ").strip()
            return ("revise", notes)
        else:
            print("Invalid choice. Please enter 'y', 'n', or 'revise'.")

if __name__ == "__main__":
    # Simple isolation test
    print("Testing approver in isolation...")
    
    test_task = {"agent": "claude", "task": "Analyze the codebase"}
    
    print("\n--- Testing Success Case ---")
    # Simulate user entering 'y'
    # result = approve(test_task, True)
    # print(f"Approver returned: {result}")
    
    print("\n--- Testing Failure Case ---")
    # Simulate user entering 'n'
    # result = approve(test_task, False)
    # print(f"Approver returned: {result}")
    
    print("Manual test recommended: uncomment the calls above and run 'python3 src/okto/approver.py'")
