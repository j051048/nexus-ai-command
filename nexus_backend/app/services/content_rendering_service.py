"""
P2 Enhancement: Content Rendering Service

Implements rich content rendering for AI responses.
Fixes Issue #17: AI responses not rendered as rich cards.
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of content that can be rendered."""
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"
    TABLE = "table"
    CHART = "chart"
    CARD = "card"
    LIST = "list"
    METRIC = "metric"
    TIMELINE = "timeline"
    ACTION = "action"
    IMAGE = "image"
    LINK = "link"
    ACCORDION = "accordion"
    TABS = "tabs"


@dataclass
class RenderedContent:
    """Rendered content block."""
    content_type: ContentType
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    styling: Dict[str, Any] = field(default_factory=dict)


class ContentRenderingService:
    """
    P2 Enhancement: Rich content rendering for AI responses.
    
    Features:
    - Markdown to rich components
    - Auto-detection of content types
    - Interactive cards and widgets
    - Chart generation
    - Action buttons
    - Accessibility support
    """
    
    # Patterns for content detection
    CODE_PATTERN = re.compile(r'```(\w*)\n([\s\S]*?)```', re.MULTILINE)
    TABLE_PATTERN = re.compile(r'\|(.+)\|\n\|[-| ]+\|\n((?:\|.+)\|\n?)+')
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    LIST_PATTERN = re.compile(r'^[\*\-\+]\s+(.+)$', re.MULTILINE)
    NUMBERED_LIST_PATTERN = re.compile(r'^\d+\.\s+(.+)$', re.MULTILINE)
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    BOLD_PATTERN = re.compile(r'\*\*([^*]+)\*\*')
    ITALIC_PATTERN = re.compile(r'\*([^*]+)\*')
    METRIC_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*([%$￥€]|美元|元|万|百万|亿)')
    
    def __init__(self):
        self._renderers = {
            ContentType.TEXT: self._render_text,
            ContentType.MARKDOWN: self._render_markdown,
            ContentType.CODE: self._render_code,
            ContentType.TABLE: self._render_table,
            ContentType.CHART: self._render_chart,
            ContentType.CARD: self._render_card,
            ContentType.LIST: self._render_list,
            ContentType.METRIC: self._render_metric,
            ContentType.ACTION: self._render_action,
        }
    
    def render(self, content: str, auto_detect: bool = True) -> List[RenderedContent]:
        """
        Render content into rich components.
        
        Args:
            content: Raw content string
            auto_detect: Whether to auto-detect content types
            
        Returns:
            List of rendered content blocks
        """
        if not content:
            return [RenderedContent(ContentType.TEXT, "")]
        
        blocks = []
        
        if auto_detect:
            blocks = self._auto_detect_and_render(content)
        else:
            blocks = [RenderedContent(ContentType.MARKDOWN, content)]
        
        return blocks
    
    def _auto_detect_and_render(self, content: str) -> List[RenderedContent]:
        """Auto-detect content types and render."""
        blocks = []
        remaining = content
        
        # Extract code blocks first
        code_blocks, remaining = self._extract_code_blocks(remaining)
        blocks.extend(code_blocks)
        
        # Extract tables
        table_blocks, remaining = self._extract_tables(remaining)
        blocks.extend(table_blocks)
        
        # Detect metrics and create metric cards
        metric_blocks = self._detect_metrics(remaining)
        if metric_blocks:
            blocks.extend(metric_blocks)
        
        # Detect lists
        list_blocks = self._detect_lists(remaining)
        if list_blocks:
            blocks.extend(list_blocks)
        
        # Remaining as markdown
        remaining = remaining.strip()
        if remaining:
            blocks.append(RenderedContent(
                ContentType.MARKDOWN,
                remaining,
                metadata={"parsed": True}
            ))
        
        return blocks
    
    def _extract_code_blocks(self, content: str) -> Tuple[List[RenderedContent], str]:
        """Extract code blocks from content."""
        blocks = []
        
        for match in self.CODE_PATTERN.finditer(content):
            language = match.group(1) or "text"
            code = match.group(2).strip()
            
            blocks.append(RenderedContent(
                ContentType.CODE,
                code,
                metadata={
                    "language": language,
                    "lines": len(code.split('\n'))
                },
                actions=[
                    {"type": "copy", "label": "复制代码", "data": code},
                    {"type": "run", "label": "运行", "data": code, "language": language}
                ]
            ))
        
        # Remove code blocks from content
        remaining = self.CODE_PATTERN.sub('', content)
        return blocks, remaining
    
    def _extract_tables(self, content: str) -> Tuple[List[RenderedContent], str]:
        """Extract tables from content."""
        blocks = []
        
        for match in self.TABLE_PATTERN.finditer(content):
            table_text = match.group(0)
            parsed = self._parse_table(table_text)
            
            blocks.append(RenderedContent(
                ContentType.TABLE,
                parsed,
                metadata={
                    "rows": len(parsed.get("rows", [])),
                    "columns": len(parsed.get("headers", []))
                },
                actions=[
                    {"type": "export", "label": "导出CSV", "data": parsed},
                    {"type": "chart", "label": "生成图表", "data": parsed}
                ]
            ))
        
        remaining = self.TABLE_PATTERN.sub('', content)
        return blocks, remaining
    
    def _parse_table(self, table_text: str) -> Dict:
        """Parse markdown table to structured data."""
        lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
        
        if len(lines) < 2:
            return {"headers": [], "rows": []}
        
        # Parse headers
        headers = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
        
        # Parse rows (skip separator line)
        rows = []
        for line in lines[2:]:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                rows.append(dict(zip(headers, cells)))
        
        return {"headers": headers, "rows": rows}
    
    def _detect_metrics(self, content: str) -> List[RenderedContent]:
        """Detect metrics in content and create metric cards."""
        blocks = []
        metrics = []
        
        for match in self.METRIC_PATTERN.finditer(content):
            value = float(match.group(1))
            unit = match.group(2)
            
            # Get surrounding context for label
            start = max(0, match.start() - 20)
            context = content[start:match.start()].strip()
            label = context.split('\n')[-1].strip() if context else ""
            
            metrics.append({
                "value": value,
                "unit": unit,
                "label": label,
                "trend": None  # Could be enhanced with comparison
            })
        
        if metrics:
            blocks.append(RenderedContent(
                ContentType.METRIC,
                metrics,
                metadata={"count": len(metrics)},
                styling={"layout": "horizontal"}
            ))
        
        return blocks
    
    def _detect_lists(self, content: str) -> List[RenderedContent]:
        """Detect lists in content."""
        blocks = []
        
        # Bullet lists
        bullet_items = [m.group(1) for m in self.LIST_PATTERN.finditer(content)]
        if bullet_items:
            blocks.append(RenderedContent(
                ContentType.LIST,
                {"type": "bullet", "items": bullet_items},
                styling={"icon": "check"}
            ))
        
        # Numbered lists
        numbered_items = [m.group(1) for m in self.NUMBERED_LIST_PATTERN.finditer(content)]
        if numbered_items:
            blocks.append(RenderedContent(
                ContentType.LIST,
                {"type": "numbered", "items": numbered_items}
            ))
        
        return blocks
    
    def _render_text(self, content: Any, **kwargs) -> Dict:
        """Render plain text."""
        return {
            "type": "text",
            "content": str(content)
        }
    
    def _render_markdown(self, content: str, **kwargs) -> Dict:
        """Render markdown content."""
        # Apply inline formatting
        rendered = content
        
        # Bold
        rendered = self.BOLD_PATTERN.sub(r'<strong>\1</strong>', rendered)
        # Italic
        rendered = self.ITALIC_PATTERN.sub(r'<em>\1</em>', rendered)
        # Links
        rendered = self.LINK_PATTERN.sub(r'<a href="\2">\1</a>', rendered)
        
        return {
            "type": "markdown",
            "content": rendered
        }
    
    def _render_code(self, content: str, metadata: Dict = None, **kwargs) -> Dict:
        """Render code block."""
        return {
            "type": "code",
            "content": content,
            "language": metadata.get("language", "text") if metadata else "text",
            "highlight": True,
            "lineNumbers": True
        }
    
    def _render_table(self, content: Dict, **kwargs) -> Dict:
        """Render table component."""
        return {
            "type": "table",
            "headers": content.get("headers", []),
            "rows": content.get("rows", []),
            "sortable": True,
            "filterable": True
        }
    
    def _render_chart(self, content: Dict, **kwargs) -> Dict:
        """Render chart from data."""
        chart_type = kwargs.get("chart_type", "bar")
        
        return {
            "type": "chart",
            "chartType": chart_type,
            "data": content,
            "options": {
                "responsive": True,
                "legend": {"position": "bottom"}
            }
        }
    
    def _render_card(self, content: Dict, **kwargs) -> Dict:
        """Render a card component."""
        return {
            "type": "card",
            "title": content.get("title", ""),
            "content": content.get("content", ""),
            "icon": content.get("icon"),
            "actions": content.get("actions", []),
            "styling": content.get("styling", {})
        }
    
    def _render_list(self, content: Dict, **kwargs) -> Dict:
        """Render list component."""
        return {
            "type": "list",
            "listType": content.get("type", "bullet"),
            "items": content.get("items", []),
            "icon": content.get("icon", "check")
        }
    
    def _render_metric(self, content: List[Dict], **kwargs) -> Dict:
        """Render metrics display."""
        return {
            "type": "metrics",
            "metrics": content,
            "layout": "horizontal"
        }
    
    def _render_action(self, content: Dict, **kwargs) -> Dict:
        """Render action button."""
        return {
            "type": "action",
            "label": content.get("label", ""),
            "action": content.get("action", "click"),
            "data": content.get("data", {}),
            "styling": content.get("styling", {"variant": "primary"})
        }
    
    def render_to_json(self, blocks: List[RenderedContent]) -> str:
        """Render blocks to JSON for frontend consumption."""
        result = []
        for block in blocks:
            renderer = self._renderers.get(block.content_type, self._render_text)
            rendered = renderer(block.content, metadata=block.metadata, **block.styling)
            rendered["metadata"] = block.metadata
            rendered["actions"] = block.actions
            result.append(rendered)
        
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    def create_rich_response(
        self,
        content: str,
        title: str = None,
        icon: str = None,
        actions: List[Dict] = None
    ) -> Dict:
        """
        Create a complete rich response with cards and actions.
        """
        blocks = self.render(content)
        
        response = {
            "version": "2.0",
            "timestamp": datetime.utcnow().isoformat(),
            "blocks": json.loads(self.render_to_json(blocks)),
            "metadata": {
                "blockCount": len(blocks),
                "hasCode": any(b.content_type == ContentType.CODE for b in blocks),
                "hasTable": any(b.content_type == ContentType.TABLE for b in blocks),
                "hasMetrics": any(b.content_type == ContentType.METRIC for b in blocks)
            }
        }
        
        if title:
            response["title"] = title
        if icon:
            response["icon"] = icon
        if actions:
            response["actions"] = actions
        
        return response
    
    def create_action_buttons(self, actions: List[Dict]) -> List[Dict]:
        """
        Create action buttons for responses.
        
        Args:
            actions: List of action definitions
            
        Returns:
            Formatted action buttons
        """
        buttons = []
        
        for action in actions:
            button = {
                "type": "button",
                "label": action.get("label", ""),
                "action": action.get("type", "click"),
                "data": action.get("data", {}),
                "styling": {
                    "variant": action.get("variant", "default"),
                    "icon": action.get("icon")
                }
            }
            buttons.append(button)
        
        return buttons


# Global instance
content_rendering_service = ContentRenderingService()
