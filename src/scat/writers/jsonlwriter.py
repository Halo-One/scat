#!/usr/bin/env python3
# coding: utf8

import binascii
import datetime
import json
from typing import Any, TextIO

from scat.writers.abstractwriter import AbstractWriter

class JsonlWriter(AbstractWriter):
    """Writes one JSON object per line.

    Every line has 'kind', 'ts' (ISO 8601 UTC, or null) and 'radio_id'. 'ts'
    is the modem's timestamp; when the parser had none and fell back to the
    host clock, the line also has 'ts_basis': 'host'. Kinds:

    - 'record': a structured record from a parser, in 'record' (its 'type'
      field names the log item, e.g. 'nr_ml1_meas_db').
    - 'cp': a control plane GSMTAP packet. 'frame' is its 1-based number in a
      PCAP written by the same run, 'data' the packet as hex.
    - 'up': a user plane packet; only 'frame' and 'length' unless
      include_up is set.

    Records carry 'last_frame', the frame number of the most recent packet,
    so a record describing a message can be matched to the packet that was
    written for it.
    """

    def __init__(self, fname: str | None = None, stream: TextIO | None = None, include_up: bool = False):
        if stream is not None:
            self.f = stream
            self.owns_file = False
        else:
            if fname is None:
                raise ValueError('JsonlWriter needs a file name or a stream')
            self.f = open(fname, 'w', buffering=1, encoding='utf-8')
            self.owns_file = True
        self.include_up = include_up
        self.frame = 0

    def __enter__(self):
        return self

    @staticmethod
    def _ts(ts: datetime.datetime | None) -> str | None:
        if ts is None:
            return None
        # Naive timestamps are the host's local time (the parsers' fallback
        # when an item carries no modem timestamp).
        return ts.astimezone(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

    def _write(self, obj: dict[str, Any], ts: datetime.datetime | None = None) -> None:
        obj['ts'] = self._ts(ts)
        if ts is not None and ts.tzinfo is None:
            obj['ts_basis'] = 'host'
        self.f.write(json.dumps(obj, separators=(',', ':'), default=str) + '\n')

    def write_cp(self, sock_content: bytes, radio_id: int = 0, ts: datetime.datetime | None = None):
        self.frame += 1
        self._write({'kind': 'cp', 'radio_id': radio_id, 'frame': self.frame,
                     'data': binascii.hexlify(sock_content).decode()}, ts)

    def write_up(self, sock_content: bytes, radio_id: int = 0, ts: datetime.datetime | None = None):
        self.frame += 1
        obj = {'kind': 'up', 'radio_id': radio_id, 'frame': self.frame, 'length': len(sock_content)}
        if self.include_up:
            obj['data'] = binascii.hexlify(sock_content).decode()
        self._write(obj, ts)

    def write_record(self, record: dict[str, Any], radio_id: int = 0, ts: datetime.datetime | None = None):
        self._write({'kind': 'record', 'radio_id': radio_id, 'last_frame': self.frame,
                     'record': record}, ts)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.owns_file:
            self.f.close()
