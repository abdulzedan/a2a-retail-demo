import os

root_dir = os.path.abspath(os.path.dirname(__file__))
output_file = os.path.join(root_dir, "all_files_with_content.txt")

# Read .gitignore patterns (simple: only supports lines ending with / or filenames)
ignore_patterns = set()
gitignore_path = os.path.join(root_dir, ".gitignore")
if os.path.exists(gitignore_path):
    with open(gitignore_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ignore_patterns.add(line)

# Always ignore .venv and the output file
ignore_patterns.update({".venv", "all_files_with_content.txt", ".git", "__pycache__"})

def should_ignore(rel_path):
    for pattern in ignore_patterns:
        # Ignore directories
        if pattern.endswith("/") and rel_path.startswith(pattern.rstrip("/")):
            return True
        # Ignore files by name
        if os.path.basename(rel_path) == pattern:
            return True
        # Ignore files by relative path
        if rel_path == pattern:
            return True
    return False

with open(output_file, "w", encoding="utf-8") as out:
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Remove ignored directories in-place
        dirnames[:] = [d for d in dirnames if not should_ignore(os.path.relpath(os.path.join(dirpath, d), root_dir))]
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
            if should_ignore(rel_path):
                continue
            file_path = os.path.join(dirpath, filename)
            out.write(f"=== {os.path.abspath(file_path)} ===\n")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f"[Could not read file: {e}]\n")
            out.write("\n\n")
print(f"Done! Output written to {output_file}")