"""
P2 Enhancement: Tool Examples Service

Provides few-shot examples for tool descriptions to improve LLM tool calling accuracy.
Fixes Issue #23: Tool descriptions lack few-shot examples.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ExampleCategory(Enum):
    """Categories of tool examples."""
    SIMPLE = "simple"           # Single parameter
    COMPLEX = "complex"         # Multiple parameters
    EDGE_CASE = "edge_case"     # Error handling
    CHAINED = "chained"         # Tool chaining
    CONDITIONAL = "conditional" # Conditional execution


@dataclass
class ToolExample:
    """Few-shot example for a tool."""
    user_query: str
    tool_name: str
    tool_args: Dict[str, Any]
    expected_result: str
    category: ExampleCategory = ExampleCategory.SIMPLE
    explanation: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)


class ToolExamplesService:
    """
    P2 Enhancement: Few-shot examples for improved tool calling.
    
    Features:
    - Predefined examples for common tools
    - Automatic example injection
    - Query-based example retrieval
    - Example validation
    - Custom example registration
    """
    
    # Default examples for common tools
    DEFAULT_EXAMPLES: Dict[str, List[ToolExample]] = {
        "search_knowledge": [
            ToolExample(
                user_query="搜索产品手册",
                tool_name="search_knowledge",
                tool_args={"query": "产品手册", "limit": 5},
                expected_result="返回5条相关产品手册文档",
                category=ExampleCategory.SIMPLE,
                explanation="简单搜索只需提供查询关键词"
            ),
            ToolExample(
                user_query="查找上周发布的销售报告",
                tool_name="search_knowledge",
                tool_args={"query": "销售报告", "filters": {"date": "last_week", "type": "report"}, "limit": 10},
                expected_result="返回上周的销售报告",
                category=ExampleCategory.COMPLEX,
                explanation="复杂搜索可添加过滤条件"
            ),
        ],
        "query_database": [
            ToolExample(
                user_query="查询本月销售额",
                tool_name="query_database",
                tool_args={"table": "sales", "columns": ["amount", "date"], "where": {"date": "this_month"}},
                expected_result="返回本月销售数据",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="统计每个部门的员工数量",
                tool_name="query_database",
                tool_args={"table": "employees", "columns": ["department", "COUNT(*) as count"], "group_by": "department"},
                expected_result="返回各部门员工统计",
                category=ExampleCategory.COMPLEX,
                explanation="聚合查询需要指定group_by"
            ),
        ],
        "send_email": [
            ToolExample(
                user_query="发送邮件给张三",
                tool_name="send_email",
                tool_args={"to": "zhangsan@example.com", "subject": "工作通知", "body": "请查收"},
                expected_result="邮件发送成功",
                category=ExampleCategory.SIMPLE,
                explanation="发送邮件需要收件人、主题和内容"
            ),
            ToolExample(
                user_query="群发会议通知给所有部门主管",
                tool_name="send_email",
                tool_args={"to": "managers@company.com", "subject": "会议通知", "body": "会议内容...", "cc": ["dept1@company.com", "dept2@company.com"]},
                expected_result="群发邮件成功",
                category=ExampleCategory.COMPLEX
            ),
        ],
        "create_task": [
            ToolExample(
                user_query="创建一个任务提醒我开会",
                tool_name="create_task",
                tool_args={"title": "参加会议", "due_date": "2024-01-15 10:00", "priority": "high"},
                expected_result="任务创建成功",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="给项目组所有人创建任务",
                tool_name="create_task",
                tool_args={"title": "项目任务", "assignees": ["user1", "user2", "user3"], "project": "project_123"},
                expected_result="批量创建任务成功",
                category=ExampleCategory.COMPLEX
            ),
        ],
        "analyze_data": [
            ToolExample(
                user_query="分析销售趋势",
                tool_name="analyze_data",
                tool_args={"dataset": "sales", "analysis_type": "trend", "time_range": "last_30_days"},
                expected_result="返回销售趋势分析结果",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="对比去年同期销售数据",
                tool_name="analyze_data",
                tool_args={"dataset": "sales", "analysis_type": "comparison", "compare_periods": ["2023-Q1", "2024-Q1"], "metrics": ["revenue", "orders"]},
                expected_result="返回同比分析结果",
                category=ExampleCategory.COMPLEX
            ),
        ],
        "get_user_info": [
            ToolExample(
                user_query="查询用户信息",
                tool_name="get_user_info",
                tool_args={"user_id": "user_123"},
                expected_result="返回用户信息",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="查询用户的历史订单",
                tool_name="get_user_info",
                tool_args={"user_id": "user_123", "include": ["orders", "history"], "limit": 20},
                expected_result="返回用户信息及订单历史",
                category=ExampleCategory.COMPLEX
            ),
        ],
        "web_search": [
            ToolExample(
                user_query="搜索最新的AI新闻",
                tool_name="web_search",
                tool_args={"query": "AI artificial intelligence news 2024", "num_results": 5},
                expected_result="返回5条AI相关新闻",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="查找竞争对手的产品定价",
                tool_name="web_search",
                tool_args={"query": "competitor pricing", "sites": ["competitor1.com", "competitor2.com"], "num_results": 10},
                expected_result="返回竞争对手定价信息",
                category=ExampleCategory.COMPLEX
            ),
        ],
        "execute_code": [
            ToolExample(
                user_query="计算100的阶乘",
                tool_name="execute_code",
                tool_args={"language": "python", "code": "import math; print(math.factorial(100))"},
                expected_result="返回计算结果",
                category=ExampleCategory.SIMPLE
            ),
            ToolExample(
                user_query="分析这个CSV文件并生成图表",
                tool_name="execute_code",
                tool_args={"language": "python", "code": "import pandas as pd; import matplotlib.pyplot as plt; ...", "files": ["data.csv"]},
                expected_result="返回图表文件",
                category=ExampleCategory.COMPLEX
            ),
        ],
    }
    
    def __init__(self):
        self._examples: Dict[str, List[ToolExample]] = dict(self.DEFAULT_EXAMPLES)
        self._query_patterns: Dict[str, List[str]] = self._build_query_patterns()
    
    def _build_query_patterns(self) -> Dict[str, List[str]]:
        """Build query pattern index for retrieval."""
        patterns = {}
        for tool_name, examples in self._examples.items():
            patterns[tool_name] = [ex.user_query for ex in examples]
        return patterns
    
    def register_example(self, example: ToolExample):
        """Register a custom example."""
        if example.tool_name not in self._examples:
            self._examples[example.tool_name] = []
        self._examples[example.tool_name].append(example)
        self._build_query_patterns()
        
    def get_examples(
        self,
        tool_name: str,
        category: ExampleCategory = None,
        limit: int = 3
    ) -> List[ToolExample]:
        """Get examples for a specific tool."""
        examples = self._examples.get(tool_name, [])
        
        if category:
            examples = [e for e in examples if e.category == category]
        
        return examples[:limit]
    
    def get_all_examples(self) -> Dict[str, List[ToolExample]]:
        """Get all registered examples."""
        return self._examples
    
    def find_similar_examples(self, query: str, limit: int = 5) -> List[ToolExample]:
        """Find examples similar to the query."""
        # Simple keyword matching
        query_lower = query.lower()
        results = []
        
        for tool_name, examples in self._examples.items():
            for example in examples:
                score = self._calculate_similarity(query_lower, example.user_query.lower())
                if score > 0:
                    results.append((score, example))
        
        # Sort by score and return top results
        results.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in results[:limit]]
    
    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """Calculate simple keyword overlap similarity."""
        words1 = set(query1.split())
        words2 = set(query2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def format_for_prompt(
        self,
        tool_name: str,
        include_explanation: bool = True,
        max_examples: int = 2
    ) -> str:
        """
        Format examples for inclusion in tool description.
        
        Returns a formatted string for LLM prompt.
        """
        examples = self.get_examples(tool_name, limit=max_examples)
        
        if not examples:
            return ""
        
        lines = ["\n示例用法:"]
        
        for i, example in enumerate(examples, 1):
            lines.append(f"\n{i}. 用户: {example.user_query}")
            lines.append(f"   调用: {example.tool_name}({json.dumps(example.tool_args, ensure_ascii=False)})")
            lines.append(f"   结果: {example.expected_result}")
            
            if include_explanation and example.explanation:
                lines.append(f"   说明: {example.explanation}")
        
        return "\n".join(lines)
    
    def format_all_for_prompt(self, tool_names: List[str] = None) -> str:
        """Format all examples for a comprehensive prompt."""
        names = tool_names or list(self._examples.keys())
        sections = []
        
        for tool_name in names:
            formatted = self.format_for_prompt(tool_name)
            if formatted:
                sections.append(f"\n### {tool_name}\n{formatted}")
        
        return "\n".join(sections)
    
    def get_tool_description_with_examples(
        self,
        tool_name: str,
        base_description: str
    ) -> str:
        """
        Enrich tool description with examples.
        
        Args:
            tool_name: Name of the tool
            base_description: Original tool description
            
        Returns:
            Enhanced description with examples
        """
        examples_text = self.format_for_prompt(tool_name)
        
        if not examples_text:
            return base_description
        
        return f"{base_description}\n{examples_text}"
    
    def validate_example(self, example: ToolExample) -> List[str]:
        """Validate an example for correctness."""
        errors = []
        
        if not example.user_query:
            errors.append("user_query is required")
        
        if not example.tool_name:
            errors.append("tool_name is required")
        
        if not example.tool_args:
            errors.append("tool_args is required")
        
        if not example.expected_result:
            errors.append("expected_result is required")
        
        return errors
    
    def export_examples(self) -> str:
        """Export examples to JSON."""
        data = {}
        for tool_name, examples in self._examples.items():
            data[tool_name] = [
                {
                    "user_query": ex.user_query,
                    "tool_args": ex.tool_args,
                    "expected_result": ex.expected_result,
                    "category": ex.category.value,
                    "explanation": ex.explanation
                }
                for ex in examples
            ]
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def import_examples(self, json_data: str):
        """Import examples from JSON."""
        data = json.loads(json_data)
        
        for tool_name, examples in data.items():
            for ex_data in examples:
                example = ToolExample(
                    user_query=ex_data["user_query"],
                    tool_name=tool_name,
                    tool_args=ex_data["tool_args"],
                    expected_result=ex_data["expected_result"],
                    category=ExampleCategory(ex_data.get("category", "simple")),
                    explanation=ex_data.get("explanation", "")
                )
                self.register_example(example)


# Global instance
tool_examples_service = ToolExamplesService()


# Convenience function
def get_tool_examples(tool_name: str, limit: int = 2) -> str:
    """Get formatted examples for a tool."""
    return tool_examples_service.format_for_prompt(tool_name, max_examples=limit)"
