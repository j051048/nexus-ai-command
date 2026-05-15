import re

with open(r'C:/Users/Fei/.gemini/antigravity/brain/62acb013-bda1-4e23-aa26-3613aaf17e5f/.system_generated/steps/306/output.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# find all table_name and column_name pairs
pairs = re.findall(r'\\?\"table_name\\?\":\\?\"(.*?)\\?\",\\?\"column_name\\?\":\\?\"(.*?)\\?\"', text)

table_to_col = {}
for table, col in pairs:
    if table not in table_to_col:
        table_to_col[table] = col
    else:
        if col == 'tenant_id':
            table_to_col[table] = col
        elif col == 'org_id' and table_to_col[table] != 'tenant_id':
            table_to_col[table] = col

sql_path = r'C:\Users\Fei\Desktop\AI应用\nexus-ai-command\supabase\migrations\20260514_p0_tenant_rls_policy_backfill.sql'
with open(sql_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    m = re.search(r'CREATE POLICY .*? ON public\.(\w+) FOR ALL USING \((.*?)::text =', line)
    if m:
        table = m.group(1)
        used_col = m.group(2)
        if table in table_to_col:
            correct_col = table_to_col[table]
            if used_col != correct_col:
                line = line.replace(f'({used_col}::text =', f'({correct_col}::text =')
                line = line.replace(f'CHECK ({used_col}::text =', f'CHECK ({correct_col}::text =')
    new_lines.append(line)

with open(sql_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('SQL fixed successfully! Processed {} tables'.format(len(table_to_col)))
