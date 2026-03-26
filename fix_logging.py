#!/usr/bin/env python3
"""
批量修复日志级别脚本
将错误相关的 logger.debug() 改为 logger.error()
"""
import os
import re

def fix_logging_levels(directory):
    """修复目录下所有 Python 文件的日志级别"""
    count = 0

    for root, dirs, files in os.walk(directory):
        # 跳过虚拟环境和缓存
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]

        for file in files:
            if not file.endswith('.py'):
                continue

            filepath = os.path.join(root, file)

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 替换包含 error/fail 的 debug 日志
            new_content = re.sub(
                r'logger\.debug\((f?"[^"]*(?:[Ee]rror|[Ff]ail)[^"]*")',
                r'logger.error(\1',
                content
            )

            if new_content != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                count += 1
                print(f"Fixed: {filepath}")

    return count

if __name__ == "__main__":
    fixed = fix_logging_levels("nexus_backend/app")
    print(f"\nCompleted! Fixed {fixed} files")
