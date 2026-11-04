#!/usr/bin/env python3
# coding: utf8

import abc
import datetime
from typing import Any

class AbstractWriter(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def write_cp(self, sock_content: bytes, radio_id: int=0, ts: datetime.datetime | None = None) -> None:
        return

    @abc.abstractmethod
    def write_up(self, sock_content: bytes, radio_id: int=0, ts: datetime.datetime | None = None) -> None:
        return

    def write_record(self, record: dict[str, Any], radio_id: int=0, ts: datetime.datetime | None = None) -> None:
        """Receives a structured (decoded) record from a parser. Writers ignore it by default."""
        return
