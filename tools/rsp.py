#!/usr/bin/env python3
"""
Minimal GDB remote-serial-protocol client for Spice86's stub.

The point of using it over the MCP server: when a breakpoint fires, the stub
PUSHES a stop packet to the client (GdbCommandBreakPointHandler.ContinueCommand
-- "CPU thread will send something when breakpoint is reached"). So a tracer
blocks on a socket read and the emulator runs at full speed in between, instead
of being paused by every read_cpu_state poll.

Packet layout: $<payload>#<2 hex checksum>, each side acking with '+'.
Registers come back as 16 values of 8 hex chars each, byte-swapped
(GdbFormatter.FormatValueAsHex32 = Swap32).
"""
import socket

# GdbCommandRegisterHandler.GetRegisterValue: 0-7 general, 8 IP, 9 flags,
# 10-15 segments.
REGS = ["ax", "cx", "dx", "bx", "sp", "bp", "si", "di",
        "ip", "flags", "cs", "ss", "ds", "es", "fs", "gs"]


def is_error(pkt):
    """A GDB error reply is exactly 'E' plus two hex digits.

    Length matters: memory whose first byte is 0xEB comes back as 'EB1F7D01',
    which `startswith("E")` calls an error and throws away a perfectly good read.
    """
    return bool(pkt) and len(pkt) == 3 and pkt[0] == "E"


class Rsp:
    def __init__(self, port, host="127.0.0.1", timeout=None):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(timeout)
        self.buf = b""
        self.stops = []          # stop packets that arrived while we asked something

    def close(self):
        self.sock.close()

    def _send(self, payload):
        body = payload.encode()
        csum = sum(body) & 0xFF
        self.sock.sendall(b"$" + body + b"#" + f"{csum:02x}".encode())

    def _read_packet(self, timeout=None):
        """Read one $...# packet, skipping acks. None on timeout."""
        old = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while True:
                start = self.buf.find(b"$")
                end = self.buf.find(b"#", start + 1) if start >= 0 else -1
                if start >= 0 and end >= 0 and len(self.buf) >= end + 3:
                    payload = self.buf[start + 1:end]
                    self.buf = self.buf[end + 3:]
                    self.sock.sendall(b"+")
                    return payload.decode(errors="replace")
                try:
                    chunk = self.sock.recv(4096)
                except socket.timeout:
                    return None
                if not chunk:
                    return None
                self.buf += chunk
        finally:
            self.sock.settimeout(old)

    @staticmethod
    def is_stop(pkt):
        return bool(pkt) and pkt[0] in "STWX"

    def cmd(self, payload, timeout=10):
        """Send a command and return its reply.

        Stop packets are asynchronous, so one can land between the command and
        its answer. Queue those instead of returning them as the reply -- doing
        otherwise turns a stop into `bad register reply: 'S05'`.
        """
        self._send(payload)
        while True:
            pkt = self._read_packet(timeout)
            if pkt is None or not self.is_stop(pkt):
                return pkt
            self.stops.append(pkt)

    def _data_reply(self, payload, want, timeout=10):
        """Send a command and return the first reply that looks like data.

        'OK' acks from an earlier continue, and stop packets pushed by the CPU
        thread, both land in this stream. Treating one of them as the answer is
        how a register read comes back as 'OK'.
        """
        self._send(payload)
        for _ in range(8):
            pkt = self._read_packet(timeout)
            if pkt is None:
                return None
            if self.is_stop(pkt):
                self.stops.append(pkt)
                continue
            if pkt == "OK":
                continue
            if want(pkt):
                return pkt
        return None

    def registers(self):
        r = self._data_reply("g", lambda p: len(p) >= 128)
        if not r or len(r) < 128:
            raise RuntimeError(f"bad register reply: {r!r}")
        out = {}
        for i, name in enumerate(REGS):
            v = int(r[i * 8:(i + 1) * 8], 16)
            out[name] = int.from_bytes(v.to_bytes(4, "big"), "little") & 0xFFFFFFFF
        return out

    def read_mem(self, linear, length):
        out = bytearray()
        while length > 0:
            take = min(length, 1024)
            r = self._data_reply(f"m{linear:x},{take:x}",
                                 lambda p: len(p) == take * 2 or is_error(p))
            if r is None or is_error(r):
                raise RuntimeError(f"read_mem {linear:#x}: {r!r}")
            out += bytes.fromhex(r)
            linear += take
            length -= take
        return bytes(out)

    def set_break(self, linear, condition=None, kind=0):
        cmd = f"Z{kind},{linear:x},1"
        if condition:
            cmd += f";X:{condition}"
        return self.cmd(cmd)

    def clear_break(self, linear, kind=0):
        return self.cmd(f"z{kind},{linear:x},1")

    def cont(self):
        """Continue.

        The stub answers 'c' with OK and the CPU thread pushes the stop packet
        later -- but when the emulator was already halted the two can arrive in
        either order, so whichever comes first is handled and a stop is queued
        rather than mistaken for the acknowledgement.
        """
        self._send("c")
        pkt = self._read_packet(5)
        if self.is_stop(pkt):
            self.stops.append(pkt)
        return pkt

    def wait_stop(self, timeout=None):
        """Block until the stub reports a stop. No polling."""
        if self.stops:
            return self.stops.pop(0)
        while True:
            pkt = self._read_packet(timeout)
            if pkt is None or self.is_stop(pkt):
                return pkt
