"""
数据导入服务 - CSV/Excel 解析和批量导入
支持员工和客户数据的批量导入，包含数据校验和错误处理
"""
import csv
import io
import re
from typing import List, Dict, Any, Optional
import logging

# Try to import openpyxl, but don't fail if not available
try:
    from openpyxl import load_workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

logger = logging.getLogger(__name__)


class ImportService:
    """数据导入服务类，处理 CSV 和 Excel 文件的解析和导入"""
    
    @staticmethod
    def _parse_file(contents: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        解析上传的文件内容（CSV 或 Excel）
        
        Args:
            contents: 文件二进制内容
            filename: 文件名（用于判断文件类型）
        
        Returns:
            解析后的数据列表，每行为一个字典
        
        Raises:
            ValueError: 文件格式不支持或解析失败
        """
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext == 'csv':
            return ImportService._parse_csv(contents)
        elif file_ext in ['xlsx', 'xls']:
            return ImportService._parse_excel(contents, file_ext)
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}")
    
    @staticmethod
    def _parse_csv(contents: bytes) -> List[Dict[str, Any]]:
        """
        解析 CSV 文件，自动检测编码（utf-8 或 gbk）
        
        Args:
            contents: CSV 文件二进制内容
        
        Returns:
            解析后的数据列表
        """
        # 尝试 UTF-8 编码
        try:
            text = contents.decode('utf-8')
        except UnicodeDecodeError:
            # 如果 UTF-8 失败，尝试 GBK
            try:
                text = contents.decode('gbk')
            except UnicodeDecodeError:
                raise ValueError("无法识别文件编码，请使用 UTF-8 或 GBK 编码")
        
        # 使用 csv.DictReader 解析
        text_io = io.StringIO(text)
        reader = csv.DictReader(text_io)
        
        data = []
        for row in reader:
            # 过滤空行
            if any(row.values()):
                data.append(row)
        
        return data
    
    @staticmethod
    def _parse_excel(contents: bytes, file_ext: str) -> List[Dict[str, Any]]:
        """
        解析 Excel 文件
        
        Args:
            contents: Excel 文件二进制内容
            file_ext: 文件扩展名
        
        Returns:
            解析后的数据列表
        """
        if not OPENPYXL_AVAILABLE:
            raise ValueError("Excel 文件解析需要 openpyxl 库，请联系管理员安装")
        
        # 使用 BytesIO 创建文件对象
        file_io = io.BytesIO(contents)
        
        try:
            # 使用只读模式加载工作簿
            workbook = load_workbook(file_io, read_only=True)
            sheet = workbook.active
            
            # 获取表头（第一行）
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return []
            
            headers = rows[0]
            data = []
            
            # 解析数据行
            for row in rows[1:]:
                # 过滤空行
                if any(row):
                    row_dict = {str(headers[i]): row[i] for i in range(len(headers)) if i < len(row)}
                    data.append(row_dict)
            
            return data
        except Exception as e:
            logger.error(f"Excel 解析失败: {e}")
            raise ValueError(f"Excel 文件解析失败: {str(e)}")
    
    @staticmethod
    async def preview(contents: bytes, filename: str) -> Dict[str, Any]:
        """
        预览导入数据（返回前10行和总行数）
        
        Args:
            contents: 文件二进制内容
            filename: 文件名
        
        Returns:
            包含 rows（前10行）和 total（总行数）的字典
        """
        try:
            data = ImportService._parse_file(contents, filename)
            return {
                "rows": data[:10],
                "total": len(data)
            }
        except Exception as e:
            logger.error(f"文件预览失败: {e}")
            raise ValueError(f"文件预览失败: {str(e)}")
    
    @staticmethod
    def get_template(template_type: str) -> str:
        """
        获取导入模板（CSV 格式）
        
        Args:
            template_type: 模板类型（employees 或 customers）
        
        Returns:
            CSV 格式的模板字符串
        """
        templates = {
            "employees": "姓名,邮箱,部门,角色,手机号",
            "customers": "客户名称,联系人,联系电话,邮箱,公司,来源,备注"
        }
        
        template = templates.get(template_type)
        if not template:
            raise ValueError(f"不支持的模板类型: {template_type}")
        
        return template
    
    @staticmethod
    def _validate_email(email: str) -> bool:
        """验证邮箱格式"""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    async def import_employees(
        contents: bytes,
        filename: str,
        user_id: str,
        db_client: Any
    ) -> Dict[str, Any]:
        """
        导入员工数据
        
        Args:
            contents: 文件二进制内容
            filename: 文件名
            user_id: 当前操作用户ID
            db_client: 数据库客户端（支持 RLS）
        
        Returns:
            导入结果统计: success_count, skip_count, error_count, errors
        """
        try:
            data = ImportService._parse_file(contents, filename)
        except Exception as e:
            logger.error(f"文件解析失败: {e}")
            return {
                "success_count": 0,
                "skip_count": 0,
                "error_count": 0,
                "errors": [f"文件解析失败: {str(e)}"]
            }
        
        success_count = 0
        skip_count = 0
        error_count = 0
        errors = []
        
        # 字段映射（兼容中英文表头）
        field_map = {
            "姓名": "name",
            "name": "name",
            "邮箱": "email",
            "email": "email",
            "部门": "department",
            "department": "department",
            "角色": "role",
            "role": "role",
            "手机号": "phone",
            "phone": "phone"
        }
        
        for idx, row in enumerate(data, start=2):  # 从第2行开始（第1行是表头）
            try:
                # 标准化字段名
                normalized_row = {}
                for k, v in row.items():
                    if k in field_map:
                        normalized_row[field_map[k]] = v
                
                # 校验必填字段
                name = normalized_row.get("name", "").strip()
                email = normalized_row.get("email", "").strip()
                
                if not name:
                    errors.append(f"第{idx}行: 姓名不能为空")
                    error_count += 1
                    continue
                
                if not email:
                    errors.append(f"第{idx}行: 邮箱不能为空")
                    error_count += 1
                    continue
                
                # 校验邮箱格式
                if not ImportService._validate_email(email):
                    errors.append(f"第{idx}行: 邮箱格式无效 ({email})")
                    error_count += 1
                    continue
                
                # 检查邮箱是否已存在
                existing = await db_client.table("users")\
                    .select("id")\
                    .eq("email", email)\
                    .maybe_single()\
                    .execute()
                
                if existing.data:
                    skip_count += 1
                    continue
                
                # 构建用户数据
                user_data = {
                    "name": name,
                    "email": email,
                    "department": normalized_row.get("department", "").strip() or None,
                    "role": normalized_row.get("role", "user").strip(),
                    "phone": normalized_row.get("phone", "").strip() or None,
                    "password": "Nexus@123",  # 默认密码
                    "score": 0,
                    "total_bonus": 0
                }
                
                # 插入数据库
                await db_client.table("users").insert(user_data).execute()
                success_count += 1
                
            except Exception as e:
                logger.error(f"第{idx}行导入失败: {e}")
                errors.append(f"第{idx}行: {str(e)}")
                error_count += 1
        
        return {
            "success_count": success_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors": errors[:20]  # 最多返回前20条错误
        }
    
    @staticmethod
    async def import_customers(
        contents: bytes,
        filename: str,
        user_id: str,
        db_client: Any
    ) -> Dict[str, Any]:
        """
        导入客户数据
        
        Args:
            contents: 文件二进制内容
            filename: 文件名
            user_id: 当前操作用户ID
            db_client: 数据库客户端（支持 RLS）
        
        Returns:
            导入结果统计: success_count, skip_count, error_count, errors
        """
        try:
            data = ImportService._parse_file(contents, filename)
        except Exception as e:
            logger.error(f"文件解析失败: {e}")
            return {
                "success_count": 0,
                "skip_count": 0,
                "error_count": 0,
                "errors": [f"文件解析失败: {str(e)}"]
            }
        
        success_count = 0
        skip_count = 0
        error_count = 0
        errors = []
        
        # 字段映射（兼容中英文表头）
        field_map = {
            "客户名称": "name",
            "name": "name",
            "联系人": "contact_person",
            "contact_person": "contact_person",
            "联系电话": "phone",
            "phone": "phone",
            "邮箱": "email",
            "email": "email",
            "公司": "company",
            "company": "company",
            "来源": "source",
            "source": "source",
            "备注": "notes",
            "notes": "notes"
        }
        
        for idx, row in enumerate(data, start=2):  # 从第2行开始
            try:
                # 标准化字段名
                normalized_row = {}
                for k, v in row.items():
                    if k in field_map:
                        normalized_row[field_map[k]] = v
                
                # 校验必填字段
                name = normalized_row.get("name", "").strip()
                
                if not name:
                    errors.append(f"第{idx}行: 客户名称不能为空")
                    error_count += 1
                    continue
                
                # 校验邮箱格式（如果提供）
                email = normalized_row.get("email", "").strip()
                if email and not ImportService._validate_email(email):
                    errors.append(f"第{idx}行: 邮箱格式无效 ({email})")
                    error_count += 1
                    continue
                
                # 检查客户是否已存在（按名称 + 公司）
                company = normalized_row.get("company", "").strip()
                query = db_client.table("customers").select("id").eq("name", name)
                
                if company:
                    query = query.eq("company", company)
                
                existing = await query.maybe_single().execute()
                
                if existing.data:
                    skip_count += 1
                    continue
                
                # 构建客户数据
                customer_data = {
                    "name": name,
                    "contact_person": normalized_row.get("contact_person", "").strip() or None,
                    "phone": normalized_row.get("phone", "").strip() or None,
                    "email": email or None,
                    "company": company or None,
                    "source": normalized_row.get("source", "").strip() or "批量导入",
                    "notes": normalized_row.get("notes", "").strip() or None,
                    "created_by": user_id
                }
                
                # 插入数据库
                await db_client.table("customers").insert(customer_data).execute()
                success_count += 1
                
            except Exception as e:
                logger.error(f"第{idx}行导入失败: {e}")
                errors.append(f"第{idx}行: {str(e)}")
                error_count += 1
        
        return {
            "success_count": success_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors": errors[:20]  # 最多返回前20条错误
        }
