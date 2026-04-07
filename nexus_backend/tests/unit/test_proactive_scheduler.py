import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.proactive_scheduler import ProactiveScheduler


class TestProactiveScheduler:
    @pytest.mark.asyncio
    async def test_scan_approval_timeouts_interaction(self):
        scheduler = ProactiveScheduler()

        # Test that _scan_approval_timeouts_loop will call the correct service
        with patch('app.services.approval_service.ApprovalService.check_approval_timeouts', new_callable=AsyncMock) as mock_method:
            mock_method.return_value = 5 # 5 timeouts processed

            # Since _scan_approval_timeouts_loop is an infinite loop, we can just test the inner logic or call it and cancel it.
            # But the logic is in the loop. We can mock asyncio.sleep to raise an exception to break the loop for testing.
            with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
                try:
                    await scheduler._scan_approval_timeouts_loop()
                except asyncio.CancelledError:
                    pass

            mock_method.assert_called_once()
