import logging
import os
from typing import Any

import arxiv

from app.core.database import supabase

logger = logging.getLogger(__name__)


class CrawlerService:
    """
    Service for the 'Scholar-Hunter' Agent (Phase 2).
    Crawls academic sources and finds leads.
    """

    @staticmethod
    def crawl_arxiv(
        query: str = "spectroscopy", max_results: int = 5
    ) -> list[dict[str, Any]]:
        """
        Crawl arXiv for latest papers in the domain.
        """
        logger.info(f"[Scholar-Hunter] Starting crawl for query: {query}")

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        results = []
        for result in search.results():
            paper_info = {
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "summary": result.summary,
                "published": str(result.published),
                "pdf_url": result.pdf_url,
                "doi": result.doi,
            }
            results.append(paper_info)

        logger.info(f"[Scholar-Hunter] Found {len(results)} papers.")
        return results

    @staticmethod
    async def analyze_and_push_lead(paper: dict[str, Any]):
        """
        Push a lead candidate to Supabase only when lead routing is configured.
        """
        try:
            match_score = float(os.getenv("CRAWLER_DEFAULT_MATCH_SCORE", "0"))
        except ValueError:
            match_score = 0.0
        target_user_id = os.getenv("CRAWLER_LEAD_TARGET_USER_ID", "")

        if not target_user_id:
            logger.warning(
                "Scholar-Hunter lead push skipped: CRAWLER_LEAD_TARGET_USER_ID is not configured"
            )
            return {"pushed": False, "reason": "target_user_not_configured"}

        if match_score > 0.85:
            logger.info(f"High potential lead found: {paper['title']}")

            # 2. Insert into DB (notifications table)
            try:
                content = (
                    "发现高潜学术线索：\n"
                    f"课题：{paper['title'][:80]}\n"
                    f"匹配度：{match_score:.0%}\n"
                    "建议跟进：请销售或市场人员复核论文摘要后再创建正式商机。"
                )

                await (
                    supabase.table("notifications")
                    .insert(
                        {
                            "user_id": target_user_id,
                            "title": "学术获客",
                            "content": content,
                            "type": "lead",  # Custom type for frontend mapping
                            "is_read": False,
                        }
                    )
                    .execute()
                )
                logger.info("Pushed lead to Frontend via Supabase.")

            except Exception as e:
                logger.error(f"Failed to push lead: {e}")
                return {"pushed": False, "reason": "db_error"}

        return {"pushed": match_score > 0.85, "score": match_score}


crawler_service = CrawlerService()
