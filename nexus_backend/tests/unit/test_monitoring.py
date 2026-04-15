import pytest
from unittest.mock import AsyncMock, patch

from app.monitoring.agent_metrics import AgentMetrics
from app.monitoring.health_monitor import AgentHealthMonitor

@pytest.mark.asyncio
async def test_record_node_execution():
    metrics = AgentMetrics()
    with patch("app.monitoring.agent_metrics.agent_node_duration.labels") as mock_dur:
        with patch("app.monitoring.agent_metrics.agent_node_success.labels") as mock_succ:
            await metrics.record_node_execution("test_node", 1.5, True)
            mock_dur.return_value.observe.assert_called_once_with(1.5)
            mock_succ.return_value.inc.assert_called_once()
            
    with patch("app.monitoring.agent_metrics.agent_node_duration.labels") as mock_dur:
        with patch("app.monitoring.agent_metrics.agent_node_failure.labels") as mock_fail:
            await metrics.record_node_execution("test_node_fail", 2.0, False)
            mock_dur.return_value.observe.assert_called_once_with(2.0)
            mock_fail.return_value.inc.assert_called_once()

@pytest.mark.asyncio
class TestAgentHealthMonitor:
    @patch("app.monitoring.health_monitor.supabase")
    async def test_get_success_rate(self, mock_supabase):
        monitor = AgentHealthMonitor()
        mock_result = AsyncMock()
        mock_result.data = 0.95
        mock_supabase.rpc.return_value.execute = AsyncMock(return_value=mock_result)

        rate = await monitor.get_success_rate(hours=1)
        assert rate == 0.95
        
        # Test error handling
        mock_supabase.rpc.side_effect = Exception("DB error")
        rate_error = await monitor.get_success_rate(days=1)
        assert rate_error == 0.0

    @patch.object(AgentHealthMonitor, "get_success_rate")
    async def test_detect_degradation(self, mock_get_rate):
        monitor = AgentHealthMonitor()
        # Degraded
        mock_get_rate.side_effect = [0.5, 0.9]  # recent, baseline
        res = await monitor.detect_degradation()
        assert res["degraded"] is True
        assert res["recent_rate"] == 0.5
        assert res["baseline_rate"] == 0.9

        # Not degraded
        mock_get_rate.side_effect = [0.85, 0.9]
        res = await monitor.detect_degradation()
        assert res["degraded"] is False

        # Zero baseline
        mock_get_rate.side_effect = [0.5, 0.0]
        res = await monitor.detect_degradation()
        assert res["degraded"] is False
        assert res["drop_percentage"] == 0

    @patch("app.services.cache_service.cache_service")
    @patch.object(AgentHealthMonitor, "compress_old_states")
    async def test_trigger_auto_recovery(self, mock_compress, mock_cache):
        monitor = AgentHealthMonitor()
        mock_compress.return_value = None
        mock_cache.clear_pattern = AsyncMock()
        
        await monitor.trigger_auto_recovery()
        mock_cache.clear_pattern.assert_called_once_with("tool_cache:*")
        mock_compress.assert_called_once()
