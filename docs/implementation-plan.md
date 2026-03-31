# Claude Code 架构融合实施方案

> 目标: 将 Claude Code 的优秀架构融入 Nexus AI Command
> 实施周期: 3 个阶段，每阶段 1-2 天

---

## 阶段一: 核心基础增强 (P0 - 立即实施)

### 1.1 Agent 记忆系统升级

**当前状态:**
- `conversation_memories` 表只有 `user_id` + `org_id` 隔离
- 记忆只存数据库，无文件备份

**改进方案:**

#### 步骤 1: 数据库 Schema 升级
```sql
-- supabase/migrations/20260331_memory_scope.sql
ALTER TABLE conversation_memories 
ADD COLUMN scope TEXT DEFAULT 'session' CHECK (scope IN ('user', 'project', 'session'));

-- 添加索引优化查询
CREATE INDEX idx_memories_scope ON conversation_memories(user_id, scope);

-- 迁移现有数据
UPDATE conversation_memories SET scope = 'session' WHERE scope IS NULL;
```

#### 步骤 2: 后端 API 增强
```python
# nexus_backend/app/services/memory_service.py

class MemoryScope(str, Enum):
    USER = "user"        # 全局记忆，跨项目共享
    PROJECT = "project"  # 项目级记忆，同项目共享
    SESSION = "session"  # 会话级记忆，仅当前会话

async def save_memory(
    content: str,
    user_id: str,
    org_id: str,
    scope: MemoryScope = MemoryScope.SESSION,
    project_id: Optional[str] = None
):
    """保存记忆，支持三层作用域"""
    # 1. 保存到数据库
    await supabase.table("conversation_memories").insert({
        "user_id": user_id,
        "org_id": org_id,
        "content": content,
        "scope": scope.value,
        "project_id": project_id if scope == MemoryScope.PROJECT else None
    })
    
    # 2. 备份到文件系统 (user/project 级)
    if scope in [MemoryScope.USER, MemoryScope.PROJECT]:
        await backup_to_filesystem(content, user_id, scope, project_id)

async def backup_to_filesystem(content, user_id, scope, project_id):
    """文件系统备份，防止数据库丢失"""
    base_dir = Path(".claude/memories")
    if scope == MemoryScope.USER:
        path = base_dir / user_id / "user-memories.jsonl"
    else:
        path = base_dir / user_id / project_id / "project-memories.jsonl"
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"content": content, "timestamp": datetime.now().isoformat()}) + "\n")
```

#### 步骤 3: 前端调用更新
```typescript
// src/lib/memoryApi.ts
export enum MemoryScope {
  USER = 'user',
  PROJECT = 'project',
  SESSION = 'session'
}

export async function saveMemory(
  content: string,
  scope: MemoryScope = MemoryScope.SESSION,
  projectId?: string
) {
  return httpClient.post('/api/memories/save', {
    content,
    scope,
    project_id: projectId
  });
}
```

**预期收益:**
- 用户偏好可跨项目共享 (scope=user)
- 项目知识可在团队内共享 (scope=project)
- 会话记忆保持隔离 (scope=session)

---

### 1.2 配置文件原子写入

**当前问题:**
- 直接写入配置文件，中断时可能损坏
- 无权限保留机制

**改进方案:**

```python
# nexus_backend/app/utils/safe_file_writer.py

import os
import tempfile
from pathlib import Path

async def atomic_write(target_path: str, content: str):
    """原子写入，防止文件损坏"""
    target = Path(target_path)
    
    # 1. 保留原文件权限
    existing_mode = None
    if target.exists():
        existing_mode = target.stat().st_mode
    
    # 2. 写入临时文件
    temp_fd, temp_path = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp"
    )
    
    try:
        with os.fdopen(temp_fd, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # 强制刷盘
        
        # 3. 恢复权限
        if existing_mode:
            os.chmod(temp_path, existing_mode)
        
        # 4. 原子替换
        os.replace(temp_path, target)
    except:
        os.unlink(temp_path)
        raise
```

**应用场景:**
- `.env` 文件更新
- 配置文件修改
- 日志轮转

---

### 1.3 错误处理标准化

**改进方案:**

```python
# nexus_backend/app/core/errors.py

# 统一错误前缀
API_ERROR_PREFIX = "API_ERROR"
DB_ERROR_PREFIX = "DB_ERROR"
AUTH_ERROR_PREFIX = "AUTH_ERROR"

def format_error_message(error_type: str, message: str, details: dict = None) -> str:
    """标准化错误消息格式"""
    base = f"[{error_type}] {message}"
    if details:
        base += f" | {json.dumps(details)}"
    return base

# 连接错误详情提取
def extract_connection_error(e: Exception) -> dict:
    """提取连接错误的详细信息"""
    return {
        "error_type": type(e).__name__,
        "message": str(e),
        "is_timeout": isinstance(e, TimeoutError),
        "is_connection_refused": "Connection refused" in str(e),
        "traceback": traceback.format_exc()
    }
```

**前端对应:**

```typescript
// src/lib/errorHandler.ts

export function isApiError(message: string): boolean {
  return message.startsWith('[API_ERROR]') || 
         message.startsWith('[DB_ERROR]') ||
         message.startsWith('[AUTH_ERROR]');
}

export function parseErrorDetails(message: string): {
  type: string;
  message: string;
  details?: any;
} {
  const match = message.match(/\[(\w+)\] (.+?)(?:\s\|\s(.+))?$/);
  if (!match) return { type: 'UNKNOWN', message };
  
  return {
    type: match[1],
    message: match[2],
    details: match[3] ? JSON.parse(match[3]) : undefined
  };
}
```

---

## 阶段二: 配置和权限优化 (P1 - 近期实施)

### 2.1 MCP autoApprove 机制

**当前状态:**
- 每次调用 MCP 工具都需要用户确认
- 频繁确认影响体验

**改进方案:**

#### 步骤 1: 配置格式扩展
```json
// .kiro/settings/mcp.json
{
  "mcpServers": {
    "github": {
      "command": "uvx",
      "args": ["mcp-server-github"],
      "autoApprove": [
        "search_repositories",
        "get_file_contents",
        "list_commits"
      ]
    }
  }
}
```

#### 步骤 2: 后端权限检查
```python
# nexus_backend/app/services/mcp_permission_service.py

class MCPPermissionService:
    def __init__(self):
        self.config = self._load_config()
    
    def is_auto_approved(self, server_name: str, tool_name: str) -> bool:
        """检查工具是否在自动批准列表"""
        server_config = self.config.get("mcpServers", {}).get(server_name, {})
        auto_approve_list = server_config.get("autoApprove", [])
        return tool_name in auto_approve_list
    
    async def check_permission(self, server_name: str, tool_name: str, user_id: str):
        """权限检查流程"""
        # 1. 检查是否自动批准
        if self.is_auto_approved(server_name, tool_name):
            return {"approved": True, "reason": "auto_approved"}
        
        # 2. 检查用户历史批准记录
        if await self._check_user_history(user_id, server_name, tool_name):
            return {"approved": True, "reason": "previously_approved"}
        
        # 3. 需要用户确认
        return {"approved": False, "reason": "requires_confirmation"}
```

**预期收益:**
- 常用工具自动批准，减少 80% 确认次数
- 保留危险操作的确认机制

---

### 2.2 多层配置合并

**改进方案:**

```python
# nexus_backend/app/core/config_merger.py

from typing import Dict, Any, List
from pathlib import Path

class ConfigMerger:
    """配置合并器: user < org < project"""
    
    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """合并多层配置，后者覆盖前者"""
        result = {}
        for config in configs:
            result = self._deep_merge(result, config)
        return result
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并字典"""
        merged = base.copy()
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    
    def load_all_configs(self, user_id: str, org_id: str, project_id: str) -> dict:
        """加载所有层级配置"""
        configs = []
        
        # 1. 用户级配置
        user_config = self._load_user_config(user_id)
        if user_config:
            configs.append(user_config)
        
        # 2. 组织级配置
        org_config = self._load_org_config(org_id)
        if org_config:
            configs.append(org_config)
        
        # 3. 项目级配置
        project_config = self._load_project_config(project_id)
        if project_config:
            configs.append(project_config)
        
        return self.merge_configs(*configs)
```

**应用场景:**
- MCP 服务器配置
- 工具权限配置
- UI 主题配置

---

### 2.3 命令别名系统

**改进方案:**

```python
# nexus_backend/app/core/command_aliases.py

DEFAULT_ALIASES = {
    "/c": "/commit",
    "/r": "/review",
    "/s": "/search",
    "/h": "/help"
}

class CommandAliasManager:
    def __init__(self):
        self.aliases = DEFAULT_ALIASES.copy()
        self._load_user_aliases()
    
    def resolve(self, command: str) -> str:
        """解析别名到实际命令"""
        return self.aliases.get(command, command)
    
    def add_alias(self, alias: str, target: str):
        """添加用户自定义别名"""
        if not alias.startswith("/"):
            alias = f"/{alias}"
        if not target.startswith("/"):
            target = f"/{target}"
        self.aliases[alias] = target
        self._save_user_aliases()
```

---

## 阶段三: 长期架构优化 (P2 - 长期规划)

### 3.1 插件系统设计

**目标:** 允许第三方开发者扩展功能

**架构设计:**

```python
# nexus_backend/app/core/plugin_system.py

class Plugin:
    """插件基类"""
    name: str
    version: str
    author: str
    
    def register_tools(self) -> List[Tool]:
        """注册工具"""
        return []
    
    def register_commands(self) -> List[Command]:
        """注册命令"""
        return []
    
    def on_load(self):
        """插件加载时调用"""
        pass
    
    def on_unload(self):
        """插件卸载时调用"""
        pass

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
    
    def load_plugin(self, plugin_path: str):
        """动态加载插件"""
        # 安全检查
        if not self._verify_plugin_signature(plugin_path):
            raise SecurityError("Plugin signature verification failed")
        
        # 加载插件
        plugin = self._import_plugin(plugin_path)
        plugin.on_load()
        self.plugins[plugin.name] = plugin
```

**插件目录结构:**
```
.claude/plugins/
  my-plugin/
    plugin.json       # 插件元数据
    __init__.py       # 插件入口
    tools/            # 自定义工具
    commands/         # 自定义命令
```

---

### 3.2 技能市场

**功能设计:**

```python
# nexus_backend/app/services/skill_marketplace.py

class SkillMarketplace:
    """技能市场服务"""
    
    async def search_skills(self, query: str, category: str = None):
        """搜索技能"""
        # 从远程仓库搜索
        pass
    
    async def install_skill(self, skill_id: str, version: str = "latest"):
        """安装技能"""
        # 1. 下载技能包
        # 2. 验证签名
        # 3. 解析依赖
        # 4. 安装到本地
        pass
    
    async def update_skill(self, skill_id: str):
        """更新技能"""
        pass
```

---

## 实施时间表

| 阶段 | 任务 | 预计时间 | 优先级 |
|------|------|----------|--------|
| **阶段一** | Agent 记忆 scope | 4h | P0 |
| | 配置文件原子写入 | 2h | P0 |
| | 错误处理标准化 | 2h | P0 |
| **阶段二** | MCP autoApprove | 3h | P1 |
| | 多层配置合并 | 3h | P1 |
| | 命令别名系统 | 2h | P1 |
| **阶段三** | 插件系统 | 2天 | P2 |
| | 技能市场 | 3天 | P2 |

---

## 立即开始: 阶段一第一步

**现在就可以做的:**

1. 创建数据库迁移文件
2. 实现 `atomic_write` 工具函数
3. 标准化错误消息格式

**执行命令:**
```bash
# 1. 创建迁移文件
touch supabase/migrations/20260331_memory_scope.sql

# 2. 创建工具模块
touch nexus_backend/app/utils/safe_file_writer.py

# 3. 更新错误处理
# 编辑 nexus_backend/app/core/errors.py
```

---

## 预期收益总结

| 改进项 | 当前痛点 | 改进后效果 | 量化指标 |
|--------|----------|------------|----------|
| Agent 记忆 scope | 记忆无法跨项目共享 | 用户偏好全局生效 | 记忆复用率 +300% |
| 原子写入 | 配置文件可能损坏 | 零配置损坏风险 | 故障率 -100% |
| 错误标准化 | 错误难以分类统计 | 日志分析效率提升 | 问题定位时间 -50% |
| MCP autoApprove | 频繁确认影响体验 | 常用工具自动批准 | 确认次数 -80% |
| 多层配置 | 配置管理混乱 | 团队配置统一管理 | 配置冲突 -90% |
| 命令别名 | 命令输入繁琐 | 快捷命令提升效率 | 输入字符 -60% |

---

**下一步:** 是否立即开始实施阶段一？我可以帮你创建迁移文件和工具函数。
