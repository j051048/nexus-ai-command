import arxiv
from typing import List, Dict, Any
from app.core.database import supabase
# import datetime

class CrawlerService:
    """
    Service for the 'Scholar-Hunter' Agent (Phase 2).
    Crawls academic sources and finds leads.
    """

    @staticmethod
    def crawl_arxiv(query: str = "spectroscopy", max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Crawl arXiv for latest papers in the domain.
        """
        print(f"🕷️ [Scholar-Hunter] Starting crawl for query: {query}")
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        results = []
        for result in search.results():
            paper_info = {
                "title": result.title,
                "authors": [a.name for a in result.authors],
                "summary": result.summary,
                "published": str(result.published),
                "pdf_url": result.pdf_url,
                "doi": result.doi
            }
            results.append(paper_info)
            
        print(f"✅ [Scholar-Hunter] Found {len(results)} papers.")
        return results

    @staticmethod
    def analyze_and_push_lead(paper: Dict[str, Any]):
        """
        Mock vector match and push to Supabase.
        In production, this would use vector_service to match SKU.
        """
        # 1. Mock Match Score (random high score for demo)
        match_score = 0.92
        
        if match_score > 0.85:
            print(f"🔥 High potential lead found: {paper['title']}")
            
            # 2. Insert into DB (notifications table)
            # This triggers the Supabase Realtime -> Frontend ActiveCard
            try:
                # We'll assign this notification to ID "1" (User) or logic based on role
                # For demo, just blasting user ID 1 or a specific user
                
                # Note: Currently we don't have a 'sales_leads' table in the context I saw,
                # but we have 'notifications' which feeds the card stream? 
                # Actually ActiveCardStream uses mock data + approvals.
                # To make this appear REALTIME, we need to insert a record that the frontend LISTENS to.
                # The frontend ActiveCardStream currently fetches 'pendingApprovals'. 
                # It does NOT seem to fetch generic notifications yet unless I modify it.
                # HOWEVER, user asked me to "Active Push via WebSocket".
                # If I utilize Supabase Realtime, I should probably create a `notifications` table record.
                # Let's insert into `notifications` table which we saw in `chat.py`.
                
                content = f"发现高潜学术线索！\n课题：《{paper['title'][:30]}...》\n匹配度：92%\n建议跟进：该实验室可能需要采购高精度光谱仪。"
                
                supabase.table("notifications").insert({
                    "user_id": "nexus-user-1", # Demo ID or fetch dynamic
                    "title": "🎓 学术获客",
                    "content": content,
                    "type": "lead", # Custom type for frontend mapping
                    "is_read": False
                }).execute()
                print("🚀 Pushed to Frontend via Supabase.")
                
            except Exception as e:
                print(f"Failed to push lead: {e}")

crawler_service = CrawlerService()
