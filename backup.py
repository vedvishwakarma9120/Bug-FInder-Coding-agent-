import os
from pathlib import Path
from typing import Dict, Set

class BackupManager:
    """
    Manages snapshots of the project directory to support safe rollback
    if the agent cannot resolve a bug after 3 attempts.
    """

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()
        self.snapshot: Dict[str, bytes] = {}
        self.original_files: Set[str] = set()

    def create_snapshot(self):
        """Captures the current state of all files inside the project directory."""
        self.snapshot.clear()
        self.original_files.clear()

        ignored_dirs = {".git", "__pycache__", ".vscode", "build", "bin", "obj"}
        ignored_exts = {".exe", ".o", ".obj"}

        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                full_path = Path(root) / file
                if full_path.suffix.lower() in ignored_exts:
                    continue
                rel_path = full_path.relative_to(self.project_dir).as_posix()
                try:
                    self.snapshot[rel_path] = full_path.read_bytes()
                    self.original_files.add(rel_path)
                except Exception as e:
                    print(f"[Warning] Failed to snapshot {rel_path}: {e}")

    def restore_snapshot(self):
        """
        Reverts all changes:
        1. Deletes any new files created during the session.
        2. Restores all original files back to their snapshotted contents.
        """
        ignored_dirs = {".git", "__pycache__", ".vscode", "build", "bin", "obj"}
        ignored_exts = {".exe", ".o", ".obj"}

        # 1. Delete newly created files
        for root, dirs, files in os.walk(self.project_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                full_path = Path(root) / file
                if full_path.suffix.lower() in ignored_exts:
                    continue
                rel_path = full_path.relative_to(self.project_dir).as_posix()
                if rel_path not in self.original_files:
                    try:
                        full_path.unlink()
                        print(f"  [Revert] Removed new file: {rel_path}")
                    except Exception as e:
                        print(f"  [Warning] Could not remove new file {rel_path}: {e}")

        # 2. Restore modified/deleted original files
        for rel_path, content in self.snapshot.items():
            full_path = self.project_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(content)

    def print_calm_message(self):
        """Displays a calm, reassuring message when 3 attempts fail and code is reverted."""
        print("\n" + "=" * 65)
        print("🌿 No worries! I was unable to solve this bug after 3 attempts.")
        print("   All changes have been safely reverted, new files removed,")
        print("   and your original code has been fully restored.")
        print("   Take your time, and we can try again whenever you're ready.")
        print("=" * 65 + "\n")
