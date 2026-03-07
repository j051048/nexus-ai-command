Run ruff check app/ --output-format=github
Error: app/routers/approval_flows.py:24:17: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:24:20: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:25:12: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:26:20: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:27:15: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:31:11: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:32:13: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:33:20: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:34:22: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:39:17: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:40:23: UP007 Use `X | Y` for type annotations
Error: app/routers/assets.py:41:13: UP007 Use `X | Y` for type annotations
Error: app/routers/attendance.py:23:15: UP007 Use `X | Y` for type annotations
Error: app/routers/attendance.py:24:18: UP007 Use `X | Y` for type annotations
Error: app/routers/attendance.py:39:13: UP007 Use `X | Y` for type annotations
Error: app/routers/certificates.py:25:14: UP007 Use `X | Y` for type annotations
Error: app/routers/certificates.py:26:17: UP007 Use `X | Y` for type annotations
Error: app/routers/certificates.py:27:18: UP007 Use `X | Y` for type annotations
Error: app/routers/certificates.py:32:21: UP007 Use `X | Y` for type annotations
Error: app/routers/expenses.py:29:14: UP007 Use `X | Y` for type annotations
Error: app/routers/inventory.py:23:13: UP007 Use `X | Y` for type annotations
Error: app/routers/inventory.py:29:18: UP007 Use `X | Y` for type annotations
Error: app/routers/inventory.py:30:13: UP007 Use `X | Y` for type annotations
Error: app/routers/mcp.py:228:5: N806 Variable `MCP_TOOL_TIMEOUT_SECONDS` in function should be lowercase
Error: app/routers/mcp.py:432:13: N806 Variable `MCP_SSE_TOOL_TIMEOUT` in function should be lowercase
Error: app/routers/org_structure.py:22:16: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:23:17: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:28:11: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:29:17: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:30:13: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:36:18: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:37:12: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:38:12: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:39:16: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:43:20: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:44:18: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:45:13: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:46:12: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:47:12: UP007 Use `X | Y` for type annotations
Error: app/routers/org_structure.py:53:20: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:23:18: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:24:15: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:25:18: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:26:20: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:30:13: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:31:18: UP007 Use `X | Y` for type annotations
Error: app/routers/work_orders.py:32:14: UP007 Use `X | Y` for type annotations
Error: app/services/asset_service.py:7:20: F401 `typing.Any` imported but unused
Error: app/services/attendance_service.py:7:37: F401 `datetime.timedelta` imported but unused
Error: app/services/enterprise_event_handlers.py:130:30: F541 f-string without any placeholders
Error: app/services/enterprise_event_handlers.py:178:30: F541 f-string without any placeholders
Error: app/services/enterprise_event_handlers.py:236:5: F841 Local variable `holder_id` is assigned to but never used
Error: app/services/organization_service.py:7:20: F401 `typing.Any` imported but unused
Error: app/services/system_config_service.py:7:20: F401 `typing.Any` imported but unused
Error: app/services/work_order_service.py:8:20: F401 `typing.Any` imported but unused
Error: app/tools/ai_insight_tools.py:76:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/ai_insight_tools.py:491:17: F541 f-string without any placeholders
Error: app/tools/ai_insight_tools.py:493:17: F541 f-string without any placeholders
Error: app/tools/ai_insight_tools.py:659:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/ai_insight_tools.py:705:17: F541 f-string without any placeholders
Error: app/tools/asset_tools.py:272:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/asset_tools.py:443:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/asset_tools.py:446:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/attendance_tools.py:154:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/attendance_tools.py:294:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/attendance_tools.py:359:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/contract_tools.py:6:1: I001 Import block is un-sorted or un-formatted
Error: app/tools/operational_tools.py:1:1: I001 Import block is un-sorted or un-formatted
Error: app/tools/organization_tools.py:70:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/organization_tools.py:142:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/organization_tools.py:146:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/organization_tools.py:451:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/project_tools.py:1:1: I001 Import block is un-sorted or un-formatted
Error: app/tools/system_config_tools.py:158:13: F841 Local variable `result` is assigned to but never used
Error: app/tools/work_order_tools.py:98:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/work_order_tools.py:102:9: SIM102 Use a single `if` statement instead of nested `if` statements
Error: app/tools/workflow_tools.py:143:31: F541 f-string without any placeholders
Error: app/tools/workflow_tools.py:175:20: F541 f-string without any placeholders
Error: app/tools/workflow_tools.py:282:20: F541 f-string without any placeholders
Error: Process completed with exit code 1.