import os

def check_largest_files(dir_path):
    files_info = []
    for root, dirs, files in os.walk(dir_path):
        if any(x in root for x in ['node_modules', '.git', 'venv', '__pycache__', '.next', 'dist', 'build', 'test_openclaw', 'tmp']):
            continue
        for f in files:
            if f in ['package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'poetry.lock']:
                continue
            if f.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.html', '.css', '.md', '.json', '.yaml', '.yml', '.sh')):
                path = os.path.join(root, f)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                        lines = sum(1 for _ in file)
                        files_info.append((path, lines))
                except Exception:
                    pass
    files_info.sort(key=lambda x: x[1], reverse=True)
    for i, (path, lines) in enumerate(files_info[:20]):
        print(f"{i+1}. {path}: {lines} lines")

try:
    check_largest_files('.')
except Exception as e:
    print(f"Error: {e}")
