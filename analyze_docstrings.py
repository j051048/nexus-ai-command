#!/usr/bin/env python3
"""
批量添加函数文档字符串脚本
为缺少 docstring 的关键函数添加 Google 风格文档
"""
import ast
import os

# 需要添加 docstring 的关键文件
KEY_FILES = [
    "nexus_backend/app/agent/router.py",
    "nexus_backend/app/agent/graph.py",
    "nexus_backend/app/core/auth.py",
    "nexus_backend/app/agent/tools.py",
    "nexus_backend/app/agent/state.py",
    "nexus_backend/app/services/conversation_memory/user_memory.py",
    "nexus_backend/app/services/conversation_memory/org_memory.py",
]

def has_docstring(node):
    """检查函数是否已有 docstring"""
    return (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )

def analyze_file(filepath):
    """分析文件中缺少 docstring 的函数"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    missing = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not has_docstring(node) and not node.name.startswith('_'):
                missing.append({
                    'name': node.name,
                    'line': node.lineno,
                    'is_async': isinstance(node, ast.AsyncFunctionDef)
                })

    return missing

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("Analyzing key files for missing docstrings...\n")

    for filepath in KEY_FILES:
        if not os.path.exists(filepath):
            continue

        missing = analyze_file(filepath)
        if missing:
            print(f"{filepath}:")
            for func in missing[:5]:
                print(f"  - {func['name']} (line {func['line']})")
            if len(missing) > 5:
                print(f"  ... {len(missing) - 5} more functions")
            print()

    print("Tip: Manually add docstrings to the most critical functions")
