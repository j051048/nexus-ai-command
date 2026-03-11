import os

def count_lines(dir_path):
    total = 0
    file_count = 0
    for root, dirs, files in os.walk(dir_path):
        if any(x in root for x in ['node_modules', '.git', 'venv', '__pycache__', '.next', 'dist', 'build', 'test_openclaw', 'test_openfang', 'tmp', 'coverage']):
            continue
        for f in files:
            if f in ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock']:
                continue
            if f.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.html', '.css', '.md', '.json', '.yaml', '.yml', '.sh')):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        lines = sum(1 for _ in file)
                        total += lines
                        file_count += 1
                except Exception:
                    pass
    return total, file_count

try:
    current_total, current_files = count_lines('.')
    print(f"Current Project: {current_total} lines in {current_files} files")
except Exception as e:
    print(f"Error: {e}")
