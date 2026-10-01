from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openplc_runtime import (  # noqa: E402
    DockerOpenPLCRuntimePool,
    ModbusDecisionTransport,
    REQUEST_ADDRESS,
)


class FakeResponse:
    def __init__(self, registers: list[int] | None = None, error: bool = False) -> None:
        self.registers = registers or []
        self.error = error

    def isError(self) -> bool:
        return self.error


class FakeOpenPLCClient:
    def __init__(self, *, acknowledge: bool = True, decision: int = 1) -> None:
        self.acknowledge = acknowledge
        self.decision = decision
        self.request: tuple[int, list[int], int] | None = None
        self.heartbeat = 10

    def write_registers(self, address: int, values: list[int], device_id: int) -> FakeResponse:
        self.request = (address, list(values), device_id)
        return FakeResponse()

    def read_holding_registers(self, address: int, *, count: int, device_id: int) -> FakeResponse:
        self.heartbeat += 1
        sequence = self.request[1][0] if self.request and self.acknowledge else 0
        return FakeResponse([self.decision, sequence, self.heartbeat])

    def close(self) -> None:
        pass


class DisconnectedOpenPLCClient(FakeOpenPLCClient):
    def read_holding_registers(self, address: int, *, count: int, device_id: int) -> FakeResponse:
        raise ConnectionError("connection replaced")


class ClosedBeforeReadyClient(FakeOpenPLCClient):
    def read_holding_registers(self, address: int, *, count: int, device_id: int) -> FakeResponse:
        raise ConnectionResetError("Docker forwarding socket opened before OpenPLC")


class OpenPLCRuntimeTests(unittest.TestCase):
    def test_fixed_transaction_returns_matching_openplc_decision(self) -> None:
        client = FakeOpenPLCClient(decision=1)
        transport = ModbusDecisionTransport(client, timeout_seconds=0.1)
        result = transport.evaluate(
            close_requested=True,
            actual_positions=0x08,
            target_mask=0x01,
            out_of_service_mask=0x08,
            trip_latched=False,
            present_current_da=0,
            current_limit_da=400,
        )

        self.assertTrue(result["allow"])
        self.assertEqual(result["requestSeq"], result["decisionSeq"])
        self.assertEqual(client.request[0], REQUEST_ADDRESS)
        self.assertEqual(client.request[1][1:], [0x08, 0x01, 0x08, 0, 0, 400])
        self.assertEqual(client.request[2], 1)

    def test_stale_decision_times_out_closed(self) -> None:
        client = FakeOpenPLCClient(acknowledge=False)
        transport = ModbusDecisionTransport(client, timeout_seconds=0.03)
        with self.assertRaises(RuntimeError):
            transport.evaluate(
                close_requested=True,
                actual_positions=0,
                target_mask=1,
                out_of_service_mask=8,
                trip_latched=False,
                present_current_da=0,
                current_limit_da=400,
            )

    def test_dropped_same_build_connection_retries_the_same_sequence(self) -> None:
        disconnected = DisconnectedOpenPLCClient()
        replacement = FakeOpenPLCClient(decision=1)
        original_connect = ModbusDecisionTransport._connect_client
        ModbusDecisionTransport._connect_client = staticmethod(lambda _host, _port: replacement)
        try:
            transport = ModbusDecisionTransport(
                disconnected,
                timeout_seconds=0.1,
                reconnect_endpoint=("127.0.0.1", 15020),
            )
            result = transport.evaluate(
                close_requested=True,
                actual_positions=0,
                target_mask=1,
                out_of_service_mask=8,
                trip_latched=False,
                present_current_da=0,
                current_limit_da=400,
            )
        finally:
            ModbusDecisionTransport._connect_client = staticmethod(original_connect)

        self.assertTrue(result["allow"])
        self.assertEqual(disconnected.request[1][0], replacement.request[1][0])
        self.assertEqual(result["requestSeq"], result["decisionSeq"])

    def test_student_runtime_slots_are_stable_and_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            pool = DockerOpenPLCRuntimePool(Path(raw_root))
            alpha = pool.compiler_for("alpha")
            beta = pool.compiler_for("beta")
            alpha_again = pool.compiler_for("alpha")
            self.assertEqual(alpha.slot, alpha_again.slot)
            self.assertNotEqual(alpha.slot, beta.slot)

    def test_runtime_readiness_requires_a_modbus_response(self) -> None:
        clients = iter([ClosedBeforeReadyClient(), FakeOpenPLCClient()])
        original_connect = ModbusDecisionTransport._connect_client
        ModbusDecisionTransport._connect_client = staticmethod(lambda _host, _port: next(clients))
        try:
            DockerOpenPLCRuntimePool._wait_for_modbus(15020, timeout_seconds=1)
        finally:
            ModbusDecisionTransport._connect_client = staticmethod(original_connect)


if __name__ == "__main__":
    unittest.main()
