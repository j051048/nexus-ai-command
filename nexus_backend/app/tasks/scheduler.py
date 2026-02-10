from celery.schedules import crontab
from app.core.celery_app import celery_app
from app.services.crawler_service import crawler_service

@celery_app.task
def crawl_arxiv_leads():
    """
    Scheduled task to run the Crawler Service.
    Daily 2:00 AM job.
    """
    # Simply sync wrapper for the service
    # In a real app we might care about async loop inside Celery, 
    # but arxiv lib is sync, so it's fine.
    
    # 1. Crawl
    papers = crawler_service.crawl_arxiv(query="Raman Spectroscopy", max_results=3)
    
    # 2. Analyze & Push
    for paper in papers:
        crawler_service.analyze_and_push_lead(paper)
    
    return f"Crawled and processed {len(papers)} papers."
