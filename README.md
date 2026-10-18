# AI-Powered Code-Fixing CLI Agent

A lightweight, plain-loop AI agent powered by Groq LLM API designed to automatically locate, inspect, and fix code bugs. Built without heavyweight frameworks like LangGraph.

---

## 📁 Folder Structure

```
agent/
├── .env                       # Environment variables (GROQ_API_KEY)
├── requirements.txt           # Python dependencies (groq, python-dotenv)
├── agent.py                   # Main CLI agent (plain loop, 3-attempt retry, rollback)
├── tools.py                   # 4 restricted code-fixing tools & schemas
├── backup.py                  # Snapshot, rollback & calm message manager
├── prompt.md                  # Requirements specification
└── test_project/              # Clean C++ reference project (bug-free)
    ├── main.cpp               # Test harness exercising utilities
    ├── utils.cpp              # Implementations (add, multiply, factorial, etc.)
    ├── utils.h                # Header definitions
    ├── compile.bat            # Windows batch compile & test runner
    └── compile.sh             # Linux/macOS bash compile & test runner
```

---

## 🛠️ Features & Design

1. **Plain Tool-Calling Loop (No LangGraph)**:
   - Uses Groq's official Python SDK directly (`groq`).
   - Standard message-passing loop: LLM decides tool calls -> tool runs -> results appended -> repeat (up to 10 iterations).
   - Automatically detects and uses tool-calling models like `openai/gpt-oss-120b` or `llama-3.3-70b-versatile`.

2. **The 5 Code-Fixing & Verification Tools**:
   - `search_files(keyword)`: Finds files matching a keyword in their filename or contents.
   - `search_in_file(path, pattern)`: Searches inside a file and returns matching line numbers and text.
   - `read_file(path, start_line, end_line)`: Reads exact line ranges with 1-indexed line numbers.
   - `replace_lines(path, start_line, end_line, new_code)`: Replaces **only** the buggy lines (never the entire file).
   - `run_tests(target_file, command)`: Automatically compiles & runs tests (`compile.bat`, `g++`, `python`, `node`) to verify code before and after fixes.

3. **Interactive Diff Approval (y/n)**:
   - Before any file edit is applied (both in CLI and Web App), an explicit Old vs. New line diff is shown.
   - Prompts the user: `Accept this change? (y/n)`.
   - On `y`: Edits are committed to disk.
   - On `n`: No edits are made, and the agent receives `"user declined"` so it can reconsider or stop.

4. **Automated Compiler & Test Verification**:
   - Whenever code is tested or fixed, the agent runs the compiler/test suite (`g++`, `python`, or `compile.bat`).
   - Displays real compiler warnings, errors, and program execution output to guarantee code correctness.

4. **Security & Sandbox Restrictions**:
   - All tools strictly enforce that file paths remain within the target project directory.
   - Prevents path traversal (`../`) and external directory access.

5. **3-Attempt Safety Net & Calm Rollback**:
   - Before attempting to fix a bug, a snapshot of all project files is created.
   - If the agent fails to resolve the bug after 3 attempts:
     - All modified files are restored to their exact original state.
     - Any newly created files during the session are deleted.
     - A calm, reassuring message is displayed:
       ```
       🌿 No worries! I was unable to solve this bug after 3 attempts.
          All changes have been safely reverted, new files removed,
          and your original code has been fully restored.
          Take your time, and we can try again whenever you're ready.
       ```

---

## 🚀 Setup & Installation

### 1. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 2. Configure Environment
Set your `GROQ_API_KEY` in the `.env` file:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```
*(Optional) You can specify a custom model in `.env`:*
```env
GROQ_MODEL=openai/gpt-oss-120b
```

---

## 💻 How to Run the Agent

### Option A: Interactive Web Studio (Browser UI)
```bash
python web_app.py
```
*Features:*
- **Monochrome Minimalist Black & White Theme**: Clean, distraction-free high-contrast design.
- **Smart Boilerplate Handling**: Automatic standard C++ header/namespace wrapper for snippet testing without missing boilerplate errors.
- **Whole-Code AI Analysis**: Inspects the entire codebase from line 1 to the end; never stops after a single error.
- **Line-by-Line Interactive Review**: Each problematic section is formatted with `Error line :`, `Error reason :`, `changement :` preview, and `[✓ Accept]` / `[✕ Decline]` buttons.
- **Automated Compiler & Test Verification**: Automatically builds and tests the staged code with the compiler (`g++`, `python`, `node`).
- **Gated Output Window**: Final code remains strictly locked until you are satisfied and the automated compiler verification passes.


### Option B: Terminal CLI Agent
```bash
python agent.py
```
*By default, the agent targets `test_project/` if present.*

You can also target any specific project folder:
```bash
python agent.py path/to/your/project
```

### Example Usage Session
```text
=================================================================
           AI-Powered Code-Fixing CLI Agent
=================================================================
Target Project: C:\llm\agent\test_project
AI Model:       openai/gpt-oss-120b
=================================================================
Type your bug description in simple English.
Type 'exit' or 'quit' to close the agent.

> In utils.cpp, the multiply function is doing addition. Please fix it.

-------------------------------------------------------
▶ [Attempt 1 of 3] Working on bug...
-------------------------------------------------------

[Step 1] Agent initiated 1 tool call(s):
  → Tool Call: search_files(keyword='utils.cpp')
    Result: Matching files:

[Step 2] Agent initiated 1 tool call(s):
  → Tool Call: read_file(end_line=20, path='utils.cpp', start_line=1)
    Result: File: utils.cpp (Lines 1-20 of 57):

[Step 3] Agent initiated 1 tool call(s):
  → Tool Call: replace_lines(...)

=================================================================
PROPOSED CHANGE: utils.cpp (Lines 11-11)
-----------------------------------------------------------------
<<< OLD CODE:
-   11 |     return a + b;
>>> NEW CODE:
+   11 |     return a * b;
=================================================================
Accept this change for utils.cpp? (y/n): y
[Diff Accepted] Applied changes to utils.cpp (lines 11-11).

[Agent Final Answer]:
The multiply function was returning `a + b` instead of `a * b`. Line 11 has been corrected.

-------------------------------------------------------
Did Attempt 1 resolve the bug? (y/n) [default: y]: y

🎉 Bug resolved successfully in Attempt 1!

> exit
Exiting agent. Goodbye!
```

---

## 🧪 Testing the C++ Project

The included `test_project/` contains 3 clean C++ files with mathematical, string, and vector utilities:
- `main.cpp`
- `utils.cpp`
- `utils.h`

### Compile & Run on Windows
```cmd
cd test_project
compile.bat
```

### Compile & Run on Linux / macOS
```bash
cd test_project
chmod +x compile.sh
./compile.sh
```

**Expected output when bug-free:**
```text
=== Running C++ Project Tests ===
5 + 7 = 12 (expected 12)
4 * 6 = 24 (expected 24)
5! = 120 (expected 120)
Uppercase of 'hello world' = 'HELLO WORLD'
'racecar' is palindrome: true
Max in {3, 9, 2, 15, 8} = 15 (expected 15)
=== All tests passed successfully! ===
```
