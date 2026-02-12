"""
P2 Enhancement: Priority Queue Service

Implements request prioritization for important requests.
Fixes Issue #38: Missing request priority queue.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


class Priority(Enum):
    """Request priority levels."""
    CRITICAL = 0    # System critical, process immediately
    HIGH = 1        # VIP users, urgent requests
    NORMAL = 2      # Standard requests
    LOW = 3         # Background tasks
    BATCH = 4       # Batch processing, lowest priority


@dataclass(order=True)
class PrioritizedRequest:
    """Request with priority for queue ordering."""
    priority: int
    timestamp: float
    request_id: str = field(compare=False)
    handler: Callable = field(compare=False)
    args: tuple = field(compare=False, default_factory=tuple)
    kwargs: dict = field(compare=False, default_factory=dict)
    user_id: str = field(compare=False, default="")
    org_id: str = field(compare=False, default="")
    request_type: str = field(compare=False, default="")
    metadata: dict = field(compare=False, default_factory=dict)
   

@dataclass
class QueueStats:
    """Queue statistics."""
    total_requests: int = 0
    processed_requests: int = 0
    failed_requests: int = 0
    avg_wait_time_ms: float = 0
    avg_process_time_ms: float = 0
    current_size: int = 0
    by_priority: Dict[str, int] = field(default_factory=dict)


class PriorityQueueService:
    """
    P2 Enhancement: Priority-based request queue.
    
    Features:
    - Multi-level priority queues
    - User/org priority boosting
    - Request rate limiting per priority
    - Queue monitoring and stats
    - Graceful degradation under load
    """
    
    # Priority boost for user roles
    ROLE_PRIORITY_BOOST = {
        "boss": -1,      # Boss users get priority boost
        "admin": -1,     # Admin gets priority boost
        "manager": 0,    # Manager gets normal priority
        "member": 0,     # Member gets normal priority
    }
    
    # Priority boost for request types
    TYPE_PRIORITY_BOOST = {
        "chat": 0,           # Normal
        "tool_call": -1,     # Higher priority
        "search": 0,         # Normal
        "analysis": 1,       # Lower priority (can wait)
        "batch": 2,          # Lowest for batch jobs
        "report": 1,         # Lower priority
    }
    
    # Rate limits per priority (requests per second)
    RATE_LIMITS = {
        Priority.CRITICAL: 100,
        Priority.HIGH: 50,
        Priority.NORMAL: 20,
        Priority.LOW: 10,
        Priority.BATCH: 5,
    }
    
    def __init__(
        self,
        max_workers: int = 10,
        max_queue_size: int = 1000,
        enable_rate_limit: bool = True
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.enable_rate_limit = enable_rate_limit
        
        self._queues: Dict[Priority, asyncio.PriorityQueue] = {}
        self._workers: list = []
        self._running = False
        self._stats = QueueStats()
        self._request_times: Dict[str, float] = {}
        self._rate_trackers: Dict[Priority, list] = defaultdict(list)
        
        # Initialize queues for each priority
        for priority in Priority:
            self._queues[priority] = asyncio.PriorityQueue()
    
    def _determine_priority(
        self,
        user_role: str = None,
        request_type: str = None,
        explicit_priority: Priority = None
    ) -> Priority:
        """Determine request priority based on factors."""
        if explicit_priority:
            return explicit_priority
        
        # Start with normal priority
        priority_value = Priority.NORMAL.value
        
        # Apply role boost
        if user_role:
            role_boost = self.ROLE_PRIORITY_BOOST.get(user_role, 0)
            priority_value = max(0, priority_value + role_boost)
        
        # Apply type boost
        if request_type:
            type_boost = self.TYPE_PRIORITY_BOOST.get(request_type, 0)
            priority_value = max(0, priority_value + type_boost)
        
        return Priority(priority_value)
    
    async def enqueue(
        self,
        handler: Callable,
        args: tuple = (),
        kwargs: dict = None,
        user_id: str = "",
        org_id: str = "",
        user_role: str = None,
        request_type: str = None,
        priority: Priority = None,
        metadata: dict = None
    ) -> str:
        """
        Add a request to the priority queue.
        
        Returns:
            request_id for tracking
        """
        import uuid
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        # Determine priority
        final_priority = self._determine_priority(
            user_role=user_role,
            request_type=request_type,
            explicit_priority=priority
        )
        
        # Check rate limit
        if self.enable_rate_limit and not self._check_rate_limit(final_priority):
            logger.warning(f"Rate limit exceeded for priority {final_priority}")
            # Downgrade to lower priority
            final_priority = Priority(min(final_priority.value + 1, Priority.BATCH.value))
        
        # Check queue size
        if self._stats.current_size >= self.max_queue_size:
            raise RuntimeError("Queue is full, request rejected")
        
        # Create prioritized request
        request = PrioritizedRequest(
            priority=final_priority.value,
            timestamp=time.time(),
            request_id=request_id,
            handler=handler,
            args=args,
            kwargs=kwargs or {},
            user_id=user_id,
            org_id=org_id,
            request_type=request_type or "",
            metadata=metadata or {}
        )
        
        # Add to appropriate queue
        await self._queues[final_priority].put(request)
        
        # Update stats
        self._stats.total_requests += 1
        self._stats.current_size += 1
        priority_name = final_priority.name
        self._stats.by_priority[priority_name] = self._stats.by_priority.get(priority_name, 0) + 1
        
        logger.debug(f"Enqueued request {request_id} with priority {final_priority.name}")
        return request_id
    
    def _check_rate_limit(self, priority: Priority) -> bool:
        """Check if rate limit allows for this priority."""
        now = time.time()
        limit = self.RATE_LIMITS.get(priority, 20)
        
        # Clean old entries
        self._rate_trackers[priority] = [
            t for t in self._rate_trackers[priority] if now - t < 1.0
        ]
        
        return len(self._rate_trackers[priority]) < limit
    
    async def start(self):
        """Start the queue workers."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"Started {self.max_workers} queue workers")
    
    async def stop(self):
        """Stop the queue workers."""
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
        
        self._workers = []
        logger.info("Stopped queue workers")
    
    async def _worker(self, worker_id: int):
        """Worker that processes requests from queues."""
        logger.debug(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Check queues in priority order
                request = None
                for priority in Priority:
                    try:
                        request = self._queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue
                
                if request is None:
                    # No requests, wait briefly
                    await asyncio.sleep(0.01)
                    continue
                
                # Track rate
                self._rate_trackers[Priority(request.priority)].append(time.time())
                
                # Process request
                await self._process_request(request)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.debug(f"Worker {worker_id} stopped")
    
    async def _process_request(self, request: PrioritizedRequest):
        """Process a single request."""
        start_time = time.time()
        wait_time = (start_time - request.timestamp) * 1000  # ms
        
        try:
            # Execute handler
            if asyncio.iscoroutinefunction(request.handler):
                result = await request.handler(*request.args, **request.kwargs)
            else:
                result = request.handler(*request.args, **request.kwargs)
            
            # Update stats
            process_time = (time.time() - start_time) * 1000
            self._stats.processed_requests += 1
            self._stats.avg_wait_time_ms = (
                (self._stats.avg_wait_time_ms * (self._stats.processed_requests - 1) + wait_time)
                / self._stats.processed_requests
            )
            self._stats.avg_process_time_ms = (
                (self._stats.avg_process_time_ms * (self._stats.processed_requests - 1) + process_time)
                / self._stats.processed_requests
            )
            
            logger.debug(
                f"Processed request {request.request_id}: "
                f"wait={wait_time:.1f}ms, process={process_time:.1f}ms"
            )
            
            return result
            
        except Exception as e:
            self._stats.failed_requests += 1
            logger.error(f"Request {request.request_id} failed: {e}")
            raise
        
        finally:
            self._stats.current_size -= 1
    
    async def process_now(
        self,
        handler: Callable,
        args: tuple = (),
        kwargs: dict = None,
        **priority_args
    ) -> Any:
        """
        Process a request immediately if capacity allows,
        otherwise add to queue.
        """
        if self._stats.current_size < self.max_workers:
            # Process immediately
            if asyncio.iscoroutinefunction(handler):
                return await handler(*args, **(kwargs or {}))
            else:
                return handler(*args, **(kwargs or {}))
        else:
            # Add to queue
            request_id = await self.enqueue(
                handler=handler,
                args=args,
                kwargs=kwargs,
                **priority_args
            )
            # Wait for result (simplified - in production use Future)
            return {"queued": True, "request_id": request_id}
    
    def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        return self._stats
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """Get current size of each priority queue."""
        return {
            priority.name: self._queues[priority].qsize()
            for priority in Priority
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status of the queue."""
        total_queued = sum(q.qsize() for q in self._queues.values())
        utilization = total_queued / self.max_queue_size if self.max_queue_size > 0 else 0
        
        status = "healthy"
        if utilization > 0.9:
            status = "critical"
        elif utilization > 0.7:
            status = "warning"
        
        return {
            "status": status,
            "running": self._running,
            "workers": self.max_workers,
            "total_queued": total_queued,
            "max_queue_size": self.max_queue_size,
            "utilization": f"{utilization:.1%}",
            "processed": self._stats.processed_requests,
            "failed": self._stats.failed_requests,
            "avg_wait_time_ms": f"{self._stats.avg_wait_time_ms:.1f}",
            "avg_process_time_ms": f"{self._stats.avg_process_time_ms:.1f}"
        }


# Global instance
priority_queue_service = PriorityQueueService()
