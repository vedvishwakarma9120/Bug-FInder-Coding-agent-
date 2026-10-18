import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

from tools import ToolExecutor, TOOL_DEFINITIONS
from backup import BackupManager

# Load environment variables from .env in current folder or parent folders
load_dotenv()

SYSTEM_PROMPT = """You are an AI-powered code-fixing assistant that locates and fixes bugs in a project.

Strict Rules:
1. You can ONLY access files inside the target project folder.
2. Make minimal edits only. Do not rewrite whole files.
3. First search or read files to locate the bug and inspect exact line numbers.
4. Use replace_lines to replace ONLY the buggy lines. Verify the line numbers and old code carefully.
5. Never replace the whole file.
6. For every change, the user will be prompted to accept or decline (y/n).
   - If the user declines, you will receive "user declined". You must respect this, rethink your approach, and try another fix or explain why it cannot be fixed.
7. You can test your changes using the run_tests tool to verify compilation and test results.
8. Once the bug is fixed, provide a clear, concise summary of what was causing the bug and what was changed.
"""

def get_best_model(client: Groq) -> str:
    """Finds an available tool-calling model, prioritizing configured model or defaults."""
    env_model = os.getenv("GROQ_MODEL")
    if env_model:
        return env_model
    try:
        available_models = [m.id for m in client.models.list().data]
        # Prefer llama-3.3-70b-versatile if accessible
        if "llama-3.3-70b-versatile" in available_models:
            return "llama-3.3-70b-versatile"
        # Otherwise fallback to powerful OSS models available on Groq
        for candidate in ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]:
            if candidate in available_models:
                return candidate
    except Exception:
        pass
    return "openai/gpt-oss-120b"

def run_bug_fixing_session(
    client: Groq,
    model: str,
    project_dir: Path,
    bug_description: str
):
    """
    Attempts to solve the bug up to 3 times.
    If unsolved after 3 attempts, rolls back all changes, removes new files,
    and displays a calm message.
    """
    backup_mgr = BackupManager(project_dir)
    backup_mgr.create_snapshot()

    max_attempts = 3
    max_iterations = 10
    is_resolved = False

    for attempt in range(1, max_attempts + 1):
        print(f"\n" + "-" * 55)
        print(f"▶ [Attempt {attempt} of {max_attempts}] Working on bug...")
        print("-" * 55)

        tool_executor = ToolExecutor(project_dir)

        # Build message history for this attempt
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if attempt == 1:
            user_msg = f"Bug description: {bug_description}"
        else:
            user_msg = (
                f"Bug description: {bug_description}\n"
                f"Notice: Attempt {attempt - 1} was unsuccessful or did not resolve the bug. "
                "The project has been reset to its clean state. Please re-investigate carefully and try a different approach."
            )

        messages.append({"role": "user", "content": user_msg})

        # Plain loop: max 10 iterations per attempt
        final_answer = None
        for step in range(1, max_iterations + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.1
                )
            except Exception as e:
                print(f"[Error] Groq API call failed: {e}")
                break

            choice = response.choices[0]
            msg = choice.message

            # Check if LLM requested tool calls
            if msg.tool_calls:
                print(f"\n[Step {step}] Agent initiated {len(msg.tool_calls)} tool call(s):")

                # Format assistant message with tool calls
                tool_calls_payload = []
                for tc in msg.tool_calls:
                    tool_calls_payload.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_payload
                })

                # Execute each tool call and append tool result
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                    except Exception:
                        fn_args = {}

                    # Short summary of args for display
                    args_summary = ", ".join(f"{k}={repr(v)}" for k, v in fn_args.items())
                    if len(args_summary) > 80:
                        args_summary = args_summary[:77] + "..."
                    print(f"  → Tool Call: {fn_name}({args_summary})")

                    # Run tool
                    tool_output = tool_executor.execute(fn_name, fn_args)

                    # Show brief tool output preview
                    out_first_line = tool_output.strip().splitlines()[0] if tool_output.strip() else "(empty)"
                    print(f"    Result: {out_first_line}")

                    # Append tool message
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(tool_output)
                    })

            else:
                # LLM finished and provided a final answer
                final_answer = msg.content or getattr(msg, "reasoning", "") or "Bug investigation completed."
                print(f"\n[Agent Final Answer]:\n{final_answer}\n")
                break

        # Check if changes were made and if user considers it resolved
        if tool_executor.changes_made:
            print("\n" + "=" * 55)
            print("🧪 RUNNING AUTOMATED COMPILATION & TESTS...")
            print("=" * 55)
            test_res = tool_executor.run_tests()
            print(f"Command: {test_res['command']}")
            print(f"Status:  {'✅ PASSED' if test_res['success'] else '❌ FAILED'}")
            print("-" * 55)
            print(test_res["output"])
            print("=" * 55)

            print("-" * 55)
            try:
                check = input(f"Did Attempt {attempt} resolve the bug? (y/n) [default: y]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                check = "n"

            if check in ("y", "yes", ""):
                print(f"\n🎉 Bug resolved successfully in Attempt {attempt}!")
                is_resolved = True

                # Notify user where the fixed code is saved and offer quick terminal copy
                modified_files = []
                for rel_path, old_bytes in backup_mgr.snapshot.items():
                    current_path = project_dir / rel_path
                    if current_path.exists() and current_path.read_bytes() != old_bytes:
                        modified_files.append(rel_path)

                if modified_files:
                    print(f"\n📋 Your corrected code is saved in:")
                    for mf in modified_files:
                        print(f"   → {project_dir / mf}")

                    try:
                        show_code = input("\nPrint full corrected code here for easy copying? (y/n) [default: y]: ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        show_code = "n"

                    if show_code in ("y", "yes", ""):
                        for mf in modified_files:
                            print("\n" + "=" * 65)
                            print(f"--- CORRECTED CODE: {mf} ---")
                            print("=" * 65)
                            print((project_dir / mf).read_text(encoding="utf-8", errors="ignore"))
                            print("=" * 65)
                break
            else:
                print(f"\nAttempt {attempt} did not resolve the bug. Resetting changes for clean retry...")
                backup_mgr.restore_snapshot()
        else:
            print(f"\nNo changes were applied in Attempt {attempt}.")
            backup_mgr.restore_snapshot()

    # If unsolved after all 3 attempts, revert everything and show calm message
    if not is_resolved:
        backup_mgr.restore_snapshot()
        backup_mgr.print_calm_message()

def main():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("\n[Error] GROQ_API_KEY environment variable is not set.")
        print("Please set GROQ_API_KEY in your environment or in a .env file.")
        sys.exit(1)

    client = Groq(api_key=api_key)
    model = get_best_model(client)

    # Determine target project directory:
    # 1. Command-line argument: python agent.py [project_path]
    # 2. Or ./bugged_code if it contains files
    # 3. Or ./test_project if exists, else current directory
    bugged_dir = Path("bugged_code")
    if len(sys.argv) > 1:
        project_dir = Path(sys.argv[1]).resolve()
    elif bugged_dir.is_dir() and any(f.is_file() for f in bugged_dir.glob("**/*")):
        project_dir = bugged_dir.resolve()
    elif Path("test_project").is_dir():
        project_dir = Path("test_project").resolve()
    else:
        project_dir = Path(".").resolve()

    print("=" * 65)
    print("           AI-Powered Code-Fixing CLI Agent")
    print("=" * 65)
    print(f"Target Project: {project_dir}")
    print(f"AI Model:       {model}")
    print("=" * 65)
    print("Type your bug description in simple English.")
    print("Type 'exit' or 'quit' to close the agent.\n")

    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting agent. Goodbye!")
            break

        if not prompt:
            continue

        if prompt.lower() in ("exit", "quit"):
            print("Exiting agent. Goodbye!")
            break

        run_bug_fixing_session(client, model, project_dir, prompt)

if __name__ == "__main__":
    main()
