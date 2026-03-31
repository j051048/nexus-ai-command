# MCP Auto-Approve 配置示例

## 配置文件位置
`.kiro/settings/mcp.json`

## 配置格式

```json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["mcp-server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      },
      "autoApprove": [
        "search_repositories",
        "get_file_contents",
        "list_commits",
        "search_code"
      ]
    },
    "filesystem": {
      "command": "uvx",
      "args": ["mcp-server-filesystem"],
      "autoApprove": [
        "read_file",
        "list_directory"
      ]
    }
  }
}
```

## 使用说明

### 1. 哪些工具应该 autoApprove？

**✅ 推荐自动批准:**
- 只读操作: `read_file`, `list_directory`, `search_code`
- 查询操作: `search_repositories`, `get_issue`, `list_commits`
- 分析操作: `analyze_data`, `generate_chart`

**❌ 不建议自动批准:**
- 写入操作: `create_file`, `delete_file`, `push_code`
- 危险操作: `execute_command`, `delete_repository`
- 付费操作: `create_deployment`, `send_email`

### 2. 配置生效

修改配置后自动生效，无需重启服务。

### 3. 安全建议

- 只对信任的 MCP 服务器启用 autoApprove
- 定期审查 autoApprove 列表
- 敏感操作始终保留用户确认
