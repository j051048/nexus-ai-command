"""
输入验证和 XSS 防护工具
放在 nexus_backend/app/core/sanitize.py
"""
import re
import html


def sanitize_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS"""
    return html.escape(text)


def sanitize_sql(text: str) -> str:
    """移除 SQL 注入风险字符（基础防护）"""
    # 注意：使用 Supabase 参数化查询是最佳实践
    dangerous = ["--", ";", "/*", "*/", "xp_", "sp_", "exec", "execute"]
    for pattern in dangerous:
        text = text.replace(pattern, "")
    return text


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """验证手机号（中国）"""
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


# 使用示例（在 Pydantic 模型中）:
# from app.core.sanitize import sanitize_html, validate_email
#
# class UserInput(BaseModel):
#     name: str
#     email: str
#
#     @field_validator('name')
#     def clean_name(cls, v):
#         return sanitize_html(v)
#
#     @field_validator('email')
#     def check_email(cls, v):
#         if not validate_email(v):
#             raise ValueError('邮箱格式不正确')
#         return v
