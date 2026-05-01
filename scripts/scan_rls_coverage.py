#!/usr/bin/env python3
"""
RLS 覆盖率扫描工具
扫描所有 migration SQL 文件，找出含 organization_id 但未启用 RLS 的表。

用法：
  python scripts/scan_rls_coverage.py
"""
import os
import re
import sys
from pathlib import Path


def main():
    migrations_dir = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
    if not migrations_dir.is_dir():
        print(f"❌ 未找到迁移目录: {migrations_dir}")
        sys.exit(1)

    sql_files = sorted(migrations_dir.glob("*.sql"))
    print(f"📂 扫描 {len(sql_files)} 个迁移文件...\n")

    # ---- 1. 收集所有含 organization_id 列的表 ----
    # 匹配: CREATE TABLE xxx ( ... organization_id ... )
    # 或: ALTER TABLE xxx ADD COLUMN organization_id
    tables_with_org_id: set[str] = set()
    
    create_table_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(\w+)",
        re.IGNORECASE,
    )
    alter_add_org_id_re = re.compile(
        r"ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ADD\s+(?:COLUMN\s+)?organization_id",
        re.IGNORECASE,
    )

    for f in sql_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        
        # 方法A: CREATE TABLE 内含 organization_id
        # 先找所有 CREATE TABLE，然后检查表体是否有 organization_id
        for match in create_table_re.finditer(content):
            table_name = match.group(1).lower()
            # 向后找到 ); 结束
            start = match.end()
            paren_depth = 0
            body = ""
            for i, ch in enumerate(content[start:], start=start):
                if ch == '(':
                    paren_depth += 1
                elif ch == ')':
                    if paren_depth == 0:
                        body = content[start:i]
                        break
                    paren_depth -= 1
            if "organization_id" in body.lower():
                tables_with_org_id.add(table_name)

        # 方法B: ALTER TABLE ADD organization_id
        for match in alter_add_org_id_re.finditer(content):
            tables_with_org_id.add(match.group(1).lower())

    # ---- 2. 收集所有已启用 RLS 的表 ----
    rls_enabled_re = re.compile(
        r"ALTER\s+TABLE\s+(?:public\.)?(\w+)\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
        re.IGNORECASE,
    )
    tables_with_rls: set[str] = set()

    for f in sql_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        for match in rls_enabled_re.finditer(content):
            tables_with_rls.add(match.group(1).lower())

    # ---- 3. 比对输出 ----
    missing_rls = sorted(tables_with_org_id - tables_with_rls)
    covered = sorted(tables_with_org_id & tables_with_rls)
    
    print(f"✅ 含 organization_id 且已启用 RLS 的表 ({len(covered)} 张):")
    for t in covered:
        print(f"   ✓ {t}")

    print()

    if missing_rls:
        print(f"🚨 含 organization_id 但 **未启用 RLS** 的表 ({len(missing_rls)} 张):")
        for t in missing_rls:
            print(f"   ✗ {t}")
        print()
        print("⚠️  上述表存在跨租户数据泄露风险，请尽快补充 RLS 策略。")
        print()
        
        # 生成修复 SQL 参考
        print("--- 参考修复 SQL ---")
        for t in missing_rls:
            print(f"""
ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation_select" ON public.{t}
  FOR SELECT USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_insert" ON public.{t}
  FOR INSERT WITH CHECK (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_update" ON public.{t}
  FOR UPDATE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );

CREATE POLICY "tenant_isolation_delete" ON public.{t}
  FOR DELETE USING (
    organization_id = (SELECT organization_id FROM users WHERE id = auth.uid())
  );
""")
        sys.exit(1)
    else:
        print("🎉 所有含 organization_id 的表均已启用 RLS！")
        sys.exit(0)


if __name__ == "__main__":
    main()
