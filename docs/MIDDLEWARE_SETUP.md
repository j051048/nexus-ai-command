# 如何使用全局异常处理中间件

## 第一步：在 main.py 中注册中间件

打开文件：`nexus_backend/app/main.py`

找到创建 FastAPI app 的地方，添加以下代码：

```python
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.middleware import (
    global_exception_handler,
    validation_exception_handler,
    http_exception_handler
)

# 在创建 app 之后添加
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
```

## 第二步：测试是否生效

重启后端服务，然后访问一个不存在的接口，应该返回统一的错误格式：

```json
{
  "success": false,
  "error": {
    "code": "HTTP_404",
    "message": "Not Found"
  }
}
```

## 好处

1. 所有未捕获的异常都会被记录到日志
2. 用户永远不会看到 Python 的错误堆栈
3. 错误格式统一，前端容易处理
