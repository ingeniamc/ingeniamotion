"""Pure-software emulation of an FSoE slave for exercising a real master handler.

No hardware is involved: :class:`FSoESlave` computes genuine protocol replies with
the ``fsoe_master`` library, and :class:`FSoENetwork` cycles PDO data between it
and a real ``FSoEMasterHandler``, mimicking the EtherCAT medium.
"""

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, TextIO

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    from fsoe_master.fsoe_master import FSOECommand, FSOEFrame

if TYPE_CHECKING:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


class ReplySource(Enum):
    """Origin of the slave's most recent reply."""

    FRESH = "fresh"
    STALE = "stale"


class StaleReplyBuffer:
    """Simulates the slave's PDO output buffer surviving a master restart.

    On real hardware the slave's last output stays in the PDO buffer when a
    master disconnects: the first cycles after a new master connects can
    re-deliver it before the slave has processed the new Reset request. The
    held reply stays available for ``HOLD_EXCHANGES`` deliveries, until fresh
    output replaces the simulated buffer.
    """

    HOLD_EXCHANGES = 3

    def __init__(self) -> None:
        self._reply: Optional[bytes] = None
        self._deliveries_remaining = 0

    def hold(self, reply: bytes) -> None:
        """Preserve a reply as the buffered output to re-deliver.

        Args:
            reply: The reply bytes left in the simulated PDO buffer.
        """
        self._reply = reply
        self._deliveries_remaining = self.HOLD_EXCHANGES

    def consume(self) -> Optional[bytes]:
        """Return the buffered reply, or None once the buffer is exhausted.

        Returns:
            The held reply bytes, or None if nothing is buffered anymore.
        """
        if self._reply is None:
            return None
        reply = self._reply
        self._deliveries_remaining -= 1
        if self._deliveries_remaining == 0:
            self._reply = None
        return reply


class FSoESlave:
    """A software FSoE slave device.

    Computes genuine replies via the ``fsoe_master`` library for framing/CRC
    generation - the replies are real protocol traffic, not fabricated
    constants.

    Because it outlives any one master connection (it's never power-cycled),
    its :class:`StaleReplyBuffer` can re-deliver a reply from a previous
    session right after a master restart.
    """

    def __init__(self) -> None:
        self._replies_ever = 0
        self._replies_this_session = 0
        self._outgoing_reply: Optional[bytes] = None
        self._stale_buffer = StaleReplyBuffer()
        self._last_reply_source = ReplySource.FRESH

    @property
    def last_reply_source(self) -> ReplySource:
        """Origin of the most recent reply."""
        return self._last_reply_source

    def compute_reply(self, request_bytes: bytes) -> bytes:
        """Compute the reply for one request.

        A Reset request arriving while a previous output is still buffered
        makes that output re-deliverable: the buffered stale reply is then
        returned instead of a fresh one until the buffer is exhausted, exactly
        what a PDO thread would briefly deliver right after a restart.

        Args:
            request_bytes: The master's current request, as raw bytes.

        Returns:
            The reply bytes.
        """
        request = FSOEFrame.frame_from_array(request_bytes)
        stale_reply = self._stale_buffered_reply(request.control.command)
        if stale_reply is not None:
            self._last_reply_source = ReplySource.STALE
            self._replies_ever += 1
            return stale_reply
        self._last_reply_source = ReplySource.FRESH
        return self._fresh_reply(request, request_bytes)

    def _stale_buffered_reply(self, command: "FSOECommand") -> Optional[bytes]:
        """Return the stale buffered reply to deliver, if any.

        A Reset request finding a leftover output moves it into the stale
        buffer and delivers it immediately - the first PDO cycle after a
        restart can deliver the previous output before the slave has processed
        the new Reset request. Further Reset requests are answered fresh,
        while any other request keeps draining the buffer.

        Args:
            command: The command of the request being answered.

        Returns:
            The stale reply bytes to deliver, or None to answer fresh.
        """
        if command == FSOECommand.RESET:
            if self._outgoing_reply is None:
                return None
            self._stale_buffer.hold(self._outgoing_reply)
            self._outgoing_reply = None
            return self._stale_buffer.consume()
        return self._stale_buffer.consume()

    def _fresh_reply(self, request: "FSOEFrame", request_bytes: bytes) -> bytes:
        """Compute a protocol-correct reply to the given request.

        The reply echoes the request's command and safe data, and answers
        with the request's own crc0. The connection_id is 0 until a session
        is established (Reset/Session); afterwards it is read directly off
        the request, which already carries the established one. The
        sequence_number counts the replies sent in the current session,
        restarting with every new Reset request - except for Reset replies
        themselves, which use the never-resetting ``_replies_ever`` counter
        only so their bytes never collide with an earlier session's Reset
        reply (the master rejects exact repeats).

        Neither sequence_number nor crc0 is transmitted on the wire - each
        side tracks them independently - so ``generate_crcs()`` produces a
        CRC the real master accepts only when fed the values above.

        Args:
            request: The parsed view of ``request_bytes``.
            request_bytes: The master's current request, as raw bytes.

        Returns:
            The reply bytes.
        """
        command = request.control.command
        data = request.get_safe_data_bytes()[: request.safe_data_size_bytes]

        if command == FSOECommand.RESET:
            self._replies_this_session = 0
            sequence_number = self._replies_ever
            connection_id = 0
        elif command == FSOECommand.SESSION:
            sequence_number = self._replies_this_session
            connection_id = 0
        else:
            sequence_number = self._replies_this_session
            connection_id = request.control.connection_id

        reply = FSOEFrame.frame_from_array(request_bytes)
        reply.control.command = command
        reply.control.connection_id = connection_id
        reply.control.sequence_number = sequence_number
        reply.control.crc0 = int(request.crcs[0])
        reply.set_safe_data_bytes(data)
        reply.generate_crcs()
        reply_bytes: bytes = reply.frame_to_array()

        self._outgoing_reply = reply_bytes
        self._replies_ever += 1
        self._replies_this_session += 1
        return reply_bytes


class ExchangeTrace:
    """Log of exchange events for debugging failing handshakes.

    Created without a path, it silently discards everything, so callers never
    need to check whether tracing is enabled.
    """

    def __init__(self, path: Optional[Path]) -> None:
        self._file: Optional[TextIO] = None
        if path is not None:
            self._file = path.open("w", encoding="utf-8")
            self._file.write("FSoE exchange trace\n")
            self._file.flush()

    def write(self, marker: str, message: str) -> None:
        """Append a marked event to the trace, if enabled.

        Args:
            marker: Short label identifying the event source.
            message: The event description.
        """
        if self._file is None:
            return
        self._file.write(f"[{marker}] {message}\n")
        self._file.flush()

    def close(self) -> None:
        """Close the trace file, if one is open."""
        if self._file is not None:
            self._file.close()
            self._file = None


class FSoENetwork:
    """The EtherCAT medium connecting a master handler to a slave device.

    Cycles PDO data between them - the only object that needs a reference to
    both sides. The slave survives a master being replaced, e.g. when a
    different master handler connects to it after a previous one disconnects -
    matching real hardware, which is never power-cycled between them.
    """

    def __init__(
        self,
        handler: "FSoEMasterHandler",
        slave: FSoESlave,
        trace_path: Optional[Path] = None,
    ) -> None:
        self.master = handler
        self.slave = slave
        self._trace = ExchangeTrace(trace_path)
        self._round = 0

    def __enter__(self) -> "FSoENetwork":
        """Return the network with its trace lifecycle managed by a context."""
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the trace when leaving the network context."""
        self.close()

    def trace(self, marker: str, message: str) -> None:
        """Append a marked event to the exchange trace, if enabled.

        Args:
            marker: Short label identifying the event source.
            message: The event description.
        """
        self._trace.write(marker, message)

    def close(self) -> None:
        """Close the exchange trace, if one is open."""
        self._trace.close()

    def replace_master(self, handler: "FSoEMasterHandler") -> None:
        """Connect a different master handler to the same slave.

        Args:
            handler: The master handler taking over the slave.
        """
        self.master = handler

    def exchange_one_round(self) -> bytes:
        """Exchange one request/reply round.

        Returns:
            The reply bytes sent.
        """
        self._round += 1
        marker = f"ROUND {self._round:02d}"
        self.trace(marker, f"state_before={self.master.state.name}")
        try:
            self.master.get_request()
            request_bytes = self.master.safety_master_pdu_map.get_item_bytes()
            self.trace(marker, f"request={request_bytes.hex(' ')}")
            reply_bytes = self.slave.compute_reply(request_bytes)
            self.trace(marker, f"reply_source={self.slave.last_reply_source.value}")
            self.trace(marker, f"reply={reply_bytes.hex(' ')}")
            self.master.safety_slave_pdu_map.set_item_bytes(reply_bytes)
            self.master.set_reply()
            self.trace(marker, f"state_after={self.master.state.name}")
            return reply_bytes
        except Exception as error:
            self.trace(f"{marker} EXCEPTION", f"{type(error).__name__}: {error}")
            raise

    def exchange_to_data(self, max_rounds: int = 20) -> list[bytes]:
        """Exchange rounds until the master's startup handshake reaches Data.

        Reusable across a real ``stop()``/``start()`` restart, or a master
        replacement: the slave's own per-session counter resets whenever it
        sees a new Reset request, matching the real master's own behavior.

        Args:
            max_rounds: Maximum number of rounds to exchange before giving up.

        Returns:
            The reply bytes sent, in order.

        Raises:
            RuntimeError: If Data state isn't reached within ``max_rounds``.
        """
        replies = []
        for _ in range(max_rounds):
            if self.master.state == FSoEState.DATA:
                return replies
            replies.append(self.exchange_one_round())
        raise RuntimeError(f"Did not reach Data state within {max_rounds} rounds")
