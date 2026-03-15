# Plugin Runtime 沙箱化设计

> 第三方插件安全执行的沙箱方案设计

## 1. 背景

Nexus AI Command 计划支持第三方插件扩展，允许企业客户和 ISV 开发自定义工具（如自定义 CRM 集成、行业特定分析等）。插件执行必须在安全隔离的沙箱中运行，防止：

- 未授权的文件系统访问
- 未授权的网络请求
- 资源耗尽 (CPU/内存/磁盘)
- 对主服务的攻击 (RCE/SSRF)
- 数据泄露

## 2. 方案对比

| 维度 | WASM (Wasmtime) | Docker 容器 | iframe sandbox | Deno Isolates |
|------|-----------------|-------------|---------------|---------------|
| **隔离级别** | 进程内沙箱 | OS 级隔离 | 浏览器沙箱 | V8 Isolate |
| **启动延迟** | ~1ms | ~500ms-2s | ~10ms | ~5ms |
| **内存开销** | ~1MB/实例 | ~50MB/容器 | 浏览器进程 | ~5MB/isolate |
| **语言支持** | Rust/C/Go/AssemblyScript | 任意 | JavaScript | TypeScript/JS |
| **网络控制** | 需要自实现 | iptables/网络策略 | 无网络 | --allow-net |
| **文件控制** | 无文件访问 | 挂载点控制 | 无文件访问 | --allow-read/write |
| **CPU/内存限制** | Fuel 机制 | cgroups | 无 | --v8-flags |
| **生态成熟度** | 中等 | 成熟 | 成熟(前端) | 成熟 |
| **适用场景** | 高性能、低延迟 | 全功能隔离 | 前端插件 | 服务端脚本 |
| **运维复杂度** | 低 | 高 | 低 | 低 |

### 2.1 方案排除

- **iframe sandbox**：仅适用于前端插件，不适合后端工具执行场景，排除。
- **Docker 容器**：隔离性最强，但启动延迟高、资源消耗大，不适合高频工具调用（每次 AI 对话可能触发多次工具调用），作为备选方案。

### 2.2 推荐方案

**主推：Deno Isolates**

理由：
1. **原生权限模型**：`--allow-net`, `--allow-read`, `--allow-env` 等细粒度权限
2. **TypeScript 原生支持**：插件开发者学习成本低
3. **启动快**：~5ms 级别，适合工具调用场景
4. **资源控制**：V8 堆内存限制、执行超时
5. **生态好**：NPM 兼容，Deno Deploy 可选托管
6. **安全审计**：Deno 团队持续进行安全审计

**备选：WASM (Wasmtime)**（用于性能敏感的计算型插件）

## 3. 架构设计

```
┌──────────────────────────────────────────────────┐
│              Nexus AI Command (主进程)             │
│                                                    │
│  ┌────────────┐    ┌──────────────────────────┐   │
│  │  AI Agent   │───>│  Plugin Manager          │   │
│  │  (LangGraph)│    │  - 加载插件清单           │   │
│  └────────────┘    │  - 权限校验               │   │
│                     │  - 调度执行               │   │
│                     └──────────┬───────────────┘   │
│                                │                    │
│                     ┌──────────▼───────────────┐   │
│                     │  Sandbox Orchestrator     │   │
│                     │  - 进程池管理             │   │
│                     │  - 资源配额执行           │   │
│                     │  - 超时控制               │   │
│                     └──────────┬───────────────┘   │
│                                │                    │
└────────────────────────────────┼────────────────────┘
                                 │ subprocess / IPC
                    ┌────────────▼────────────────┐
                    │     Deno Sandbox Process     │
                    │  ┌─────────────────────┐    │
                    │  │  Plugin Code         │    │
                    │  │  (TypeScript)        │    │
                    │  └──────────┬──────────┘    │
                    │             │                │
                    │  ┌──────────▼──────────┐    │
                    │  │  Plugin API (受限)   │    │
                    │  │  - nexus.db.query()  │    │
                    │  │  - nexus.http.get()  │    │
                    │  │  - nexus.log()       │    │
                    │  └─────────────────────┘    │
                    │                              │
                    │  权限: --allow-net=api.x.com │
                    │  内存: --v8-flags=--max-old-  │
                    │        space-size=64          │
                    │  超时: 30s deadline           │
                    └──────────────────────────────┘
```

## 4. 权限模型

### 4.1 权限类型

```typescript
interface PluginPermissions {
  // 网络访问 ACL
  network: {
    allowed_hosts: string[];      // ["api.example.com", "*.internal.com"]
    denied_hosts: string[];       // ["169.254.169.254"] (AWS metadata)
    allowed_ports: number[];      // [443, 8080]
    max_connections: number;      // 10
  };

  // 文件系统 ACL（仅限插件数据目录）
  filesystem: {
    read: string[];               // ["/plugins/{id}/data/"]
    write: string[];              // ["/plugins/{id}/data/"]
    max_file_size_mb: number;     // 10
    max_total_size_mb: number;    // 100
  };

  // 数据库 ACL
  database: {
    allowed_tables: string[];     // ["sales_leads", "customers"]
    operations: string[];         // ["select", "insert"]  (no delete/drop)
    max_rows_per_query: number;   // 1000
    row_level_filter: string;     // "tenant_id = '{tenant_id}'"
  };

  // Nexus API 访问
  api: {
    allowed_endpoints: string[];  // ["crm.getCustomer", "crm.listLeads"]
    rate_limit_per_minute: number; // 60
  };
}
```

### 4.2 权限级别

| 级别 | 网络 | 文件 | 数据库 | API | 用例 |
|------|------|------|--------|-----|------|
| **Minimal** | 无 | 只读自身数据 | SELECT 指定表 | 只读 API | 数据分析插件 |
| **Standard** | 白名单域名 | 读写自身目录 | SELECT+INSERT | 读写 API | CRM 集成插件 |
| **Extended** | 广泛网络访问 | 读写 + 临时文件 | SELECT+INSERT+UPDATE | 全部 API | 数据同步插件 |
| **Privileged** | 全网络 | 全文件 | 全操作 | 全部 API | 仅内部插件 |

### 4.3 默认拒绝的操作

无论任何权限级别，以下操作始终被禁止：

- 访问环境变量 (`--deny-env`)
- 访问 `169.254.169.254` (云 metadata)
- 执行子进程 (`--deny-run`)
- 访问 FFI (`--deny-ffi`)
- DROP/TRUNCATE/ALTER 数据库操作
- 访问其他租户数据
- 修改系统配置表

## 5. 资源配额

### 5.1 配额配置

```python
@dataclass
class ResourceQuota:
    """每次插件执行的资源限制"""

    # CPU
    max_execution_time_ms: int = 30_000     # 30 秒超时
    max_cpu_time_ms: int = 10_000           # 10 秒 CPU 时间

    # 内存
    max_memory_mb: int = 64                  # 64 MB 堆内存
    max_stack_size_mb: int = 2               # 2 MB 栈

    # I/O
    max_network_requests: int = 50           # 单次执行最多 50 个网络请求
    max_response_size_mb: int = 5            # 单个响应最大 5 MB
    max_db_queries: int = 20                 # 单次执行最多 20 次数据库查询

    # 输出
    max_output_size_kb: int = 256            # 返回结果最大 256 KB
    max_log_lines: int = 1000               # 最多 1000 行日志
```

### 5.2 配额执行机制

```python
class SandboxOrchestrator:
    """管理沙箱进程的生命周期和资源配额"""

    async def execute_plugin(
        self,
        plugin_id: str,
        function: str,
        args: dict,
        permissions: PluginPermissions,
        quota: ResourceQuota,
        tenant_id: str,
    ) -> PluginResult:
        # 1. 构建 Deno 命令
        cmd = [
            "deno", "run",
            "--no-prompt",
            f"--allow-net={','.join(permissions.network.allowed_hosts)}",
            f"--v8-flags=--max-old-space-size={quota.max_memory_mb}",
            # 注入 Plugin API 和参数
            "plugin_runner.ts",
            "--plugin", plugin_id,
            "--function", function,
            "--args", json.dumps(args),
            "--tenant", tenant_id,
        ]

        # 2. 启动子进程
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._safe_env(),  # 清理后的环境变量
        )

        # 3. 超时控制
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=quota.max_execution_time_ms / 1000,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return PluginResult(
                success=False,
                error="Plugin execution timed out",
                execution_time_ms=quota.max_execution_time_ms,
            )

        # 4. 解析结果
        return self._parse_result(stdout, stderr, proc.returncode)
```

## 6. Plugin API 接口设计

### 6.1 SDK 接口 (TypeScript)

```typescript
// plugin-sdk.d.ts — 插件开发者使用的 API

declare namespace Nexus {
  /** 数据库查询（受权限和行级过滤控制） */
  namespace db {
    function query(table: string, filters?: Record<string, any>): Promise<any[]>;
    function insert(table: string, data: Record<string, any>): Promise<any>;
    function update(table: string, id: string, data: Record<string, any>): Promise<any>;
  }

  /** HTTP 请求（受白名单域名控制） */
  namespace http {
    function get(url: string, options?: RequestOptions): Promise<Response>;
    function post(url: string, body: any, options?: RequestOptions): Promise<Response>;
  }

  /** 日志（限制行数，自动收集到插件日志表） */
  namespace log {
    function info(message: string, data?: any): void;
    function warn(message: string, data?: any): void;
    function error(message: string, data?: any): void;
  }

  /** 键值存储（插件专属，受配额限制） */
  namespace kv {
    function get(key: string): Promise<string | null>;
    function set(key: string, value: string, ttl_seconds?: number): Promise<void>;
    function delete(key: string): Promise<void>;
  }

  /** 执行上下文 */
  namespace context {
    const tenant_id: string;
    const user_id: string;
    const plugin_id: string;
    const execution_id: string;
  }
}
```

### 6.2 插件清单 (manifest.json)

```json
{
  "id": "crm-salesforce-sync",
  "name": "Salesforce CRM 同步",
  "version": "1.0.0",
  "author": "Acme Corp",
  "description": "将 Nexus 客户数据同步到 Salesforce",

  "entrypoint": "index.ts",

  "permissions": {
    "network": {
      "allowed_hosts": ["*.salesforce.com", "login.salesforce.com"]
    },
    "database": {
      "allowed_tables": ["sales_leads", "customers"],
      "operations": ["select"]
    },
    "api": {
      "allowed_endpoints": ["crm.getCustomer", "crm.listLeads"]
    }
  },

  "tools": [
    {
      "name": "sync_to_salesforce",
      "description": "将客户数据同步到 Salesforce",
      "parameters": {
        "type": "object",
        "properties": {
          "customer_id": { "type": "string" },
          "sync_mode": { "type": "string", "enum": ["full", "incremental"] }
        },
        "required": ["customer_id"]
      }
    }
  ],

  "resource_quota": {
    "max_execution_time_ms": 60000,
    "max_memory_mb": 128
  }
}
```

### 6.3 插件示例

```typescript
// index.ts — Salesforce 同步插件

export async function sync_to_salesforce(args: {
  customer_id: string;
  sync_mode: string;
}): Promise<string> {
  // 1. 从 Nexus 数据库读取客户数据
  const customers = await Nexus.db.query("sales_leads", {
    id: args.customer_id,
  });

  if (customers.length === 0) {
    return "客户不存在";
  }

  const customer = customers[0];
  Nexus.log.info("Syncing customer to Salesforce", { id: customer.id });

  // 2. 调用 Salesforce API
  const sfToken = await Nexus.kv.get("sf_access_token");
  const resp = await Nexus.http.post(
    "https://my.salesforce.com/services/data/v58.0/sobjects/Lead",
    {
      FirstName: customer.contact_name?.split(" ")[0],
      LastName: customer.contact_name?.split(" ").slice(1).join(" "),
      Email: customer.contact_email,
      Company: customer.company_name,
    },
    { headers: { Authorization: `Bearer ${sfToken}` } }
  );

  if (resp.ok) {
    Nexus.log.info("Sync successful", { sf_id: (await resp.json()).id });
    return `同步成功，Salesforce Lead ID: ${(await resp.json()).id}`;
  } else {
    Nexus.log.error("Sync failed", { status: resp.status });
    return `同步失败: ${resp.statusText}`;
  }
}
```

## 7. 安全通信协议

### 7.1 主进程 ↔ 沙箱 IPC

```
主进程 (Python)  ←── stdin/stdout JSON-RPC ──→  沙箱 (Deno)

Request:
{
  "jsonrpc": "2.0",
  "id": "exec-001",
  "method": "execute",
  "params": {
    "function": "sync_to_salesforce",
    "args": {"customer_id": "xxx"},
    "context": {
      "tenant_id": "t1",
      "user_id": "u1",
      "execution_id": "e1",
      "permissions": {...},
      "quota": {...}
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": "exec-001",
  "result": {
    "success": true,
    "output": "同步成功...",
    "metrics": {
      "execution_time_ms": 1200,
      "memory_peak_mb": 12,
      "network_requests": 2,
      "db_queries": 1
    },
    "logs": [
      {"level": "info", "message": "Syncing customer...", "timestamp": "..."}
    ]
  }
}
```

### 7.2 沙箱 → 主进程 API 调用

插件内的 `Nexus.db.query()` 等 API 调用通过 IPC 转发给主进程：

```
沙箱 → 主进程:
{
  "jsonrpc": "2.0",
  "id": "api-001",
  "method": "nexus.db.query",
  "params": {
    "table": "sales_leads",
    "filters": {"id": "xxx"}
  }
}

主进程进行权限检查后返回:
{
  "jsonrpc": "2.0",
  "id": "api-001",
  "result": [{"id": "xxx", "contact_name": "..."}]
}
```

**安全保证**：
- 所有 API 调用经过主进程的权限检查层
- 自动注入 `tenant_id` 过滤条件
- 数据库操作限制在允许的表和操作类型
- 网络请求限制在白名单域名

## 8. 实施路径

### Phase 1：核心沙箱（2 周）
- Deno 子进程管理器
- 基础权限模型
- stdin/stdout IPC 通信
- 超时和内存限制

### Phase 2：Plugin API（2 周）
- Plugin SDK (TypeScript 类型定义)
- db/http/log/kv API 实现
- 权限检查中间层
- 插件清单解析

### Phase 3：集成到 AI Agent（1 周）
- 插件工具注册到 tool registry
- AI Agent 调用插件工具
- 执行结果反馈到对话

### Phase 4：管理与市场（2 周）
- 插件安装/卸载 API
- 插件审核流程
- 执行监控仪表盘
- 插件市场 UI
