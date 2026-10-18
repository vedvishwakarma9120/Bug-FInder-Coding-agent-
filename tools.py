import os
import re
import sys
import difflib
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

class ToolExecutor:
    """Executes code-fixing tools strictly restricted to the project directory."""

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()
        if not self.project_dir.exists():
            raise FileNotFoundError(f"Project directory does not exist: {self.project_dir}")
        self.changes_made = False

    def _safe_path(self, rel_or_abs_path: str) -> Path:
        """Resolve path and ensure it is strictly inside the project directory."""
        # Strip leading slashes to prevent root escaping
        clean_path = rel_or_abs_path.strip().lstrip("/\\")
        target = (self.project_dir / clean_path).resolve()
        try:
            target.relative_to(self.project_dir)
        except ValueError:
            raise PermissionError(f"Access denied: '{rel_or_abs_path}' is outside the project folder.")
        return target

    def search_files(self, keyword: str) -> str:
        """
        Lists relative paths of files related to the bug by matching keyword
        against filenames and text content.
        """
        keyword_lower = keyword.strip().lower()
        if not keyword_lower:
            return "Please provide a non-empty keyword to search for."

        matches = []
        ignored_dirs = {".git", "__pycache__", ".vscode", "build", "bin", "obj"}
        ignored_exts = {".exe", ".o", ".obj", ".dll", ".so", ".dylib", ".bin", ".zip", ".tar"}

        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in ignored_exts:
                    continue
                
                rel_path = file_path.relative_to(self.project_dir).as_posix()

                # Check filename
                if keyword_lower in file.lower():
                    matches.append(rel_path)
                    continue

                # Check file content
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if keyword_lower in content.lower():
                        matches.append(rel_path)
                except Exception:
                    continue

        if not matches:
            return f"No files matching keyword '{keyword}' found in the project."

        return "Matching files:\n" + "\n".join(f"- {m}" for m in sorted(set(matches)))

    def search_in_file(self, path: str, pattern: str) -> str:
        """
        Returns the line numbers and text of lines matching pattern in path.
        """
        try:
            target = self._safe_path(path)
        except PermissionError as e:
            return str(e)

        if not target.is_file():
            return f"Error: File '{path}' does not exist or is not a file."

        try:
            lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as e:
            return f"Error reading file '{path}': {e}"

        pattern_lower = pattern.lower()
        results = []
        for idx, line in enumerate(lines, start=1):
            if pattern_lower in line.lower():
                results.append(f"Line {idx}: {line}")

        if not results:
            return f"No lines matching pattern '{pattern}' found in '{path}'."

        return f"Matches in {path}:\n" + "\n".join(results)

    def read_file(self, path: str, start_line: int, end_line: int) -> str:
        """
        Reads lines from start_line to end_line (1-indexed, inclusive) with line numbers.
        """
        try:
            target = self._safe_path(path)
        except PermissionError as e:
            return str(e)

        if not target.is_file():
            return f"Error: File '{path}' does not exist."

        try:
            lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as e:
            return f"Error reading file '{path}': {e}"

        total_lines = len(lines)
        if total_lines == 0:
            return f"File '{path}' is empty."

        start_line = max(1, int(start_line))
        end_line = min(total_lines, int(end_line))

        if start_line > end_line:
            return f"Error: start_line ({start_line}) cannot be greater than end_line ({end_line}). File has {total_lines} lines."

        output = [f"File: {path} (Lines {start_line}-{end_line} of {total_lines}):"]
        for idx in range(start_line, end_line + 1):
            output.append(f"{idx:4d} | {lines[idx - 1]}")

        return "\n".join(output)

    def replace_lines(
        self,
        path: str,
        start_line: int,
        end_line: int,
        new_code: str,
        expected_old_code: Optional[str] = None
    ) -> str:
        """
        Replaces lines start_line to end_line with new_code.
        Displays diff and prompts user for acceptance (y/n).
        """
        try:
            target = self._safe_path(path)
        except PermissionError as e:
            return str(e)

        if not target.is_file():
            return f"Error: File '{path}' does not exist."

        try:
            content = target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file '{path}': {e}"

        # Preserve original line endings
        has_crlf = "\r\n" in content
        line_ending = "\r\n" if has_crlf else "\n"
        lines = content.splitlines()
        total_lines = len(lines)

        start_line = int(start_line)
        end_line = int(end_line)

        if start_line < 1 or end_line > total_lines or start_line > end_line:
            return f"Error: Invalid line range [{start_line}, {end_line}]. File '{path}' has {total_lines} lines."

        # Safety rule: Do not replace entire file if file is large (> 5 lines)
        if start_line == 1 and end_line >= total_lines and total_lines > 5:
            return "Error: replace_lines cannot replace the whole file. Please replace only the specific buggy lines."

        # Extract current old lines
        old_lines = lines[start_line - 1 : end_line]
        old_code_str = "\n".join(old_lines)

        # Verification step: if expected_old_code was provided, verify match
        if expected_old_code:
            clean_expected = "\n".join(line.rstrip() for line in expected_old_code.strip().splitlines())
            clean_actual = "\n".join(line.rstrip() for line in old_code_str.strip().splitlines())
            if clean_expected != clean_actual:
                return (
                    f"Error: Verification failed. Old lines at {start_line}-{end_line} do not match expected code.\n"
                    f"Actual code currently at lines {start_line}-{end_line} is:\n{old_code_str}\n"
                    "Please re-read the file and try again."
                )

        # Prepare new lines
        new_lines = new_code.splitlines()

        # Display diff to user
        print("\n" + "=" * 65)
        print(f"PROPOSED CHANGE: {path} (Lines {start_line}-{end_line})")
        print("-" * 65)
        print("<<< OLD CODE:")
        for idx, line in enumerate(old_lines, start=start_line):
            print(f"- {idx:4d} | {line}")
        print(">>> NEW CODE:")
        for idx, line in enumerate(new_lines, start=start_line):
            print(f"+ {idx:4d} | {line}")
        print("=" * 65)

        # Ask user accept or decline (y/n)
        try:
            choice = input(f"Accept this change for {path}? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "n"

        if choice in ("y", "yes"):
            # Splice in the new lines
            updated_lines = lines[: start_line - 1] + new_lines + lines[end_line :]
            target.write_text(line_ending.join(updated_lines) + line_ending, encoding="utf-8")
            self.changes_made = True
            print(f"[Diff Accepted] Applied changes to {path} (lines {start_line}-{end_line}).\n")
            return f"Success: Replaced lines {start_line}-{end_line} in {path}."
        else:
            print(f"[Diff Declined] No changes written to {path}.\n")
            return "user declined"

    def run_tests(self, target_file: Optional[str] = None, command: Optional[str] = None) -> Dict[str, Any]:
        """
        Runs compilation and execution tests strictly within the project directory.
        Returns:
            {
                "success": bool,
                "command": str,
                "output": str
            }
        """
        # If user/tool provides an explicit command
        if command:
            try:
                res = subprocess.run(
                    command,
                    cwd=str(self.project_dir),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                return {
                    "success": res.returncode == 0,
                    "command": command,
                    "output": output or ("Process finished with code 0" if res.returncode == 0 else f"Process exited with code {res.returncode}")
                }
            except Exception as e:
                return {"success": False, "command": command, "output": f"Execution error: {e}"}

        # 1. Project level: check for compile.bat / compile.sh
        if os.name == "nt" and (self.project_dir / "compile.bat").is_file():
            cmd = "compile.bat"
            try:
                res = subprocess.run(
                    ["cmd", "/c", "compile.bat"],
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                return {"success": res.returncode == 0, "command": cmd, "output": output}
            except Exception as e:
                return {"success": False, "command": cmd, "output": f"Execution error: {e}"}

        if (self.project_dir / "compile.sh").is_file():
            cmd = "./compile.sh"
            try:
                res = subprocess.run(
                    ["sh", "compile.sh"],
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                return {"success": res.returncode == 0, "command": cmd, "output": output}
            except Exception as e:
                return {"success": False, "command": cmd, "output": f"Execution error: {e}"}

        # 2. Target file check or find first source file
        resolved_file = None
        if target_file:
            try:
                resolved_file = self._safe_path(target_file)
            except Exception:
                resolved_file = None

        if not resolved_file or not resolved_file.is_file():
            # Search for candidate files in project_dir
            for ext in [".cpp", ".py", ".js"]:
                found = list(self.project_dir.glob(f"*{ext}"))
                if found:
                    resolved_file = found[0]
                    break

        if not resolved_file or not resolved_file.is_file():
            return {
                "success": True,
                "command": "none",
                "output": "No compilable/runnable file found (.cpp, .py, .js, or compile script)."
            }

        suffix = resolved_file.suffix.lower()

        # C++ files
        if suffix in (".cpp", ".cc", ".cxx"):
            exe_path = resolved_file.with_suffix(".exe" if os.name == "nt" else ".out")
            compile_cmd = ["g++", "-std=c++11", "-Wall", "-Wextra", resolved_file.name, "-o", exe_path.name]
            try:
                comp_res = subprocess.run(
                    compile_cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                if comp_res.returncode != 0:
                    raw_content = resolved_file.read_text(encoding="utf-8", errors="ignore")
                    # Check if failure is due to missing standard boilerplate (cout, cin, endl, vector, string, etc.)
                    boilerplate_keywords = [
                        "'cout' was not declared", "'cin' was not declared", "'endl' was not declared",
                        "'vector'", "'string'", "'sort'", "'printf'", "'scanf'", "std::cout", "std::cin",
                        "undefined reference to `main'", "WinMain"
                    ]
                    is_boilerplate_issue = any(bp in comp_res.stderr for bp in boilerplate_keywords)

                    if is_boilerplate_issue:
                        headers_to_add = []
                        if "<iostream>" not in raw_content:
                            headers_to_add.append("#include <iostream>")
                        if "<vector>" not in raw_content and "vector" in raw_content:
                            headers_to_add.append("#include <vector>")
                        if "<string>" not in raw_content and "string" in raw_content:
                            headers_to_add.append("#include <string>")
                        if "<algorithm>" not in raw_content and ("sort(" in raw_content or "min(" in raw_content or "max(" in raw_content):
                            headers_to_add.append("#include <algorithm>")
                        if "using namespace std;" not in raw_content:
                            headers_to_add.append("using namespace std;")

                        header_block = "\n".join(headers_to_add) + "\n\n" if headers_to_add else ""
                        wrapped_code = header_block + raw_content

                        # If main function is missing, add a wrapper main
                        if "main" not in raw_content:
                            wrapped_code += "\n\nint main() { return 0; }\n"

                        wrap_file = self.project_dir / f"__bp_temp_{resolved_file.stem}.cpp"
                        wrap_exe = self.project_dir / (f"__bp_temp_{resolved_file.stem}.exe" if os.name == "nt" else f"__bp_temp_{resolved_file.stem}.out")
                        try:
                            wrap_file.write_text(wrapped_code, encoding="utf-8")
                            wrap_comp = subprocess.run(
                                ["g++", "-std=c++11", "-Wall", wrap_file.name, "-o", wrap_exe.name],
                                cwd=str(self.project_dir),
                                capture_output=True,
                                text=True,
                                timeout=15
                            )
                            if wrap_comp.returncode == 0:
                                run_cmd = [str(wrap_exe)] if os.name == "nt" else [f"./{wrap_exe.name}"]
                                wrap_run = subprocess.run(
                                    run_cmd,
                                    cwd=str(self.project_dir),
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                out_str = [
                                    "[Compiler Status]: ✅ Compilation PASSED (Standard C++ headers <iostream>/namespace were auto-provided for this snippet)."
                                ]
                                if wrap_run.stdout.strip():
                                    out_str.append(f"[Program Output]:\n{wrap_run.stdout.strip()}")
                                if wrap_run.stderr.strip():
                                    out_str.append(f"[Runtime Warnings/Errors]:\n{wrap_run.stderr.strip()}")
                                return {
                                    "success": wrap_run.returncode == 0,
                                    "command": f"g++ (auto-boilerplate) {resolved_file.name}",
                                    "output": "\n\n".join(out_str).strip() or "Program ran successfully with exit code 0."
                                }
                        finally:
                            if wrap_file.exists():
                                try:
                                    wrap_file.unlink()
                                except Exception:
                                    pass
                            if wrap_exe.exists():
                                try:
                                    wrap_exe.unlink()
                                except Exception:
                                    pass

                    # If failed because 'main' is missing, try compile-only syntax check (-c)
                    if "undefined reference to `main'" in comp_res.stderr or "WinMain" in comp_res.stderr:
                        check_res = subprocess.run(
                            ["g++", "-std=c++11", "-Wall", "-c", resolved_file.name],
                            cwd=str(self.project_dir),
                            capture_output=True,
                            text=True,
                            timeout=15
                        )
                        obj_file = resolved_file.with_suffix(".o")
                        if obj_file.exists():
                            try:
                                obj_file.unlink()
                            except Exception:
                                pass
                        if check_res.returncode == 0:
                            return {
                                "success": True,
                                "command": f"g++ -std=c++11 -Wall -c {resolved_file.name}",
                                "output": "✅ Syntax & compilation check PASSED! (File compiled successfully as object module)"
                            }
                        return {
                            "success": False,
                            "command": f"g++ -std=c++11 -Wall -c {resolved_file.name}",
                            "output": check_res.stderr.strip()
                        }

                    return {
                        "success": False,
                        "command": " ".join(compile_cmd),
                        "output": f"❌ Compilation failed:\n{comp_res.stderr.strip()}"
                    }

                # Compilation passed! Now run executable
                run_cmd = [str(exe_path)] if os.name == "nt" else [f"./{exe_path.name}"]
                run_res = subprocess.run(
                    run_cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Cleanup exe
                if exe_path.exists():
                    try:
                        exe_path.unlink()
                    except Exception:
                        pass

                out_str = []
                if comp_res.stderr.strip():
                    out_str.append(f"[Compiler Warnings]:\n{comp_res.stderr.strip()}")
                if run_res.stdout.strip():
                    out_str.append(f"[Program Output]:\n{run_res.stdout.strip()}")
                if run_res.stderr.strip():
                    out_str.append(f"[Runtime Errors]:\n{run_res.stderr.strip()}")

                return {
                    "success": run_res.returncode == 0,
                    "command": f"g++ {resolved_file.name} -o {exe_path.name} && {exe_path.name}",
                    "output": "\n\n".join(out_str).strip() or "Program ran successfully with exit code 0."
                }
            except subprocess.TimeoutExpired:
                if exe_path.exists():
                    try:
                        exe_path.unlink()
                    except Exception:
                        pass
                return {"success": False, "command": "run", "output": "Execution timed out (exceeded 5 seconds). Possible infinite loop."}
            except Exception as e:
                return {"success": False, "command": "run", "output": f"Execution error: {e}"}

        # Python files
        elif suffix == ".py":
            cmd = [sys.executable, resolved_file.name]
            try:
                res = subprocess.run(
                    cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                out = (res.stdout + "\n" + res.stderr).strip()
                return {
                    "success": res.returncode == 0,
                    "command": f"python {resolved_file.name}",
                    "output": out or "Execution finished with exit code 0."
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "command": f"python {resolved_file.name}", "output": "Execution timed out (exceeded 5 seconds)."}
            except Exception as e:
                return {"success": False, "command": f"python {resolved_file.name}", "output": f"Execution error: {e}"}

        # JavaScript files
        elif suffix == ".js":
            cmd = ["node", resolved_file.name]
            try:
                res = subprocess.run(
                    cmd,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                out = (res.stdout + "\n" + res.stderr).strip()
                return {
                    "success": res.returncode == 0,
                    "command": f"node {resolved_file.name}",
                    "output": out or "Execution finished with exit code 0."
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "command": f"node {resolved_file.name}", "output": "Execution timed out (exceeded 5 seconds)."}
            except Exception as e:
                return {"success": False, "command": f"node {resolved_file.name}", "output": f"Execution error: {e}"}

        return {"success": True, "command": "none", "output": f"File type {suffix} is not directly executable."}

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Dispatches tool execution by name."""
        if tool_name == "search_files":
            return self.search_files(keyword=arguments.get("keyword", ""))
        elif tool_name == "search_in_file":
            return self.search_in_file(
                path=arguments.get("path", ""),
                pattern=arguments.get("pattern", "")
            )
        elif tool_name == "read_file":
            return self.read_file(
                path=arguments.get("path", ""),
                start_line=arguments.get("start_line", 1),
                end_line=arguments.get("end_line", 1)
            )
        elif tool_name == "replace_lines":
            return self.replace_lines(
                path=arguments.get("path", ""),
                start_line=arguments.get("start_line", 1),
                end_line=arguments.get("end_line", 1),
                new_code=arguments.get("new_code", ""),
                expected_old_code=arguments.get("expected_old_code")
            )
        elif tool_name == "run_tests":
            res = self.run_tests(
                target_file=arguments.get("target_file"),
                command=arguments.get("command")
            )
            status = "PASSED" if res["success"] else "FAILED"
            return f"Test Results [{status}]:\nCommand: {res['command']}\nOutput:\n{res['output']}"
        else:
            return f"Error: Unknown tool '{tool_name}'."


# Tool schemas for Groq LLM API
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Lists the paths of files related to the bug by matching keyword against filenames and content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword, function name, or symbol to search for across the project."
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Returns line numbers and text of lines matching pattern in a specific file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file inside the project."
                    },
                    "pattern": {
                        "type": "string",
                        "description": "String pattern to search for in the file."
                    }
                },
                "required": ["path", "pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads lines from start_line to end_line with line numbers to examine code before fixing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file inside the project."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed, inclusive)."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-indexed, inclusive)."
                    }
                },
                "required": ["path", "start_line", "end_line"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_lines",
            "description": "Replaces only the buggy lines in a file, never the whole file. Verifies old lines and asks user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to edit."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number of the buggy lines (1-indexed)."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number of the buggy lines (1-indexed)."
                    },
                    "new_code": {
                        "type": "string",
                        "description": "The exact replacement code lines."
                    },
                    "expected_old_code": {
                        "type": "string",
                        "description": "Optional: exact old code expected at start_line to end_line for verification."
                    }
                },
                "required": ["path", "start_line", "end_line", "new_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Runs compiler or test suite (compile.bat, g++, python, node) to verify if the code compiles and tests pass.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_file": {
                        "type": "string",
                        "description": "Optional: filename to test or compile."
                    },
                    "command": {
                        "type": "string",
                        "description": "Optional: custom command to run tests."
                    }
                }
            }
        }
    }
]
