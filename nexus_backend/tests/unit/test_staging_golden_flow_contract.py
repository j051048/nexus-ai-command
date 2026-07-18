import importlib.util
import sys
from pathlib import Path


def _load_runner_module():
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "run_staging_golden_flows.py"
    spec = importlib.util.spec_from_file_location("staging_golden_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_staging_sse_parser_requires_explicit_completion() -> None:
    module = _load_runner_module()
    payloads, completed = module.parse_sse_payloads(
        'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n' "data: [DONE]\n\n"
    )
    assert completed is True
    assert payloads[0]["choices"][0]["delta"]["content"] == "ok"


def test_staging_runner_requires_isolated_tenant_credentials(monkeypatch) -> None:
    module = _load_runner_module()
    for name in module.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    try:
        module.StagingGoldenConfig.from_env()
    except module.GoldenFlowError as error:
        assert "STAGING_GOLDEN_ORG_ID" in str(error)
    else:
        raise AssertionError("staging runner accepted an unconfigured environment")
