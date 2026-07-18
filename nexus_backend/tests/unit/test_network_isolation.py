import socket

import pytest


def test_external_network_is_blocked_by_default() -> None:
    with pytest.raises(RuntimeError, match="Unexpected external network request"):
        socket.getaddrinfo("unexpected-test-network.invalid", 443)
