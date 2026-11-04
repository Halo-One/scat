#!/usr/bin/env python3

import binascii
import datetime
import io
import json
import unittest
from collections import namedtuple

import scat.parsers.qualcomm.diagcmd as diagcmd
from scat.parsers.qualcomm.diagnrlogparser import DiagNrLogParser
from scat.parsers.qualcomm.qualcommparser import QualcommParser
from scat.writers import JsonlWriter

log_header = namedtuple('QcDiagLogHeader', 'cmd_code reserved length1 length2 log_id timestamp')
c = diagcmd.diag_log_code_5gnr


def header(code, payload):
    return log_header(cmd_code=0x10, reserved=0, length1=len(payload) + 12, length2=len(payload) + 12,
                      log_id=diagcmd.diag_log_get_lte_item_id(code), timestamp=0)


class TestNrRecords(unittest.TestCase):
    parser = DiagNrLogParser(parent=None)

    def test_ml1_meas_db(self):
        payload = binascii.unhexlify('070002000114000026ffffff44000000991006000100c602000000000000000000000000ffffffffffff0000ffffffffc6027e000100000017caffff0afaffff000000000000000000000000a5a1dbbd4199a005a3bcffff17caffff17caffff0afaffff0000000000000000')
        result = self.parser.parse_nr_ml1_meas_db_update(header(c.LOG_5GNR_ML1_MEAS_DATABASE_UPDATE, payload), payload, dict())
        self.assertEqual(result['records'], [{
            'type': 'nr_ml1_meas_db', 'version': '2.7',
            'layers': [{
                'arfcn': 397465, 'serving_pci': 710, 'serving_ssb': 0,
                'serving_rsrp': [None, None], 'serving_rx_beam': [None, None],
                'cells': [{
                    'pci': 710, 'pbch_sfn': 126, 'rsrp': -107.8203125, 'rsrq': -11.921875,
                    'beams': [{'ssb_index': 0, 'rx_beam': [0, 0], 'rsrp': [-134.7265625, -107.8203125],
                               'filtered_rsrp': -107.8203125, 'filtered_rsrq': -11.921875}],
                }],
            }],
        }])

    def test_mib(self):
        payload = binascii.unhexlify('030000005001c0ac05009a00003f')
        result = self.parser.parse_nr_mib_info(header(c.LOG_5GNR_RRC_MIB_INFO, payload), payload, dict())
        self.assertEqual(result['records'], [{'type': 'nr_mib', 'arfcn': 371904, 'pci': 336, 'sfn': 154, 'scs_khz': 15}])

    def test_serving_cell(self):
        payload = binascii.unhexlify('040000009d02e0ca0900d6c609005a005a0000127df204000000060102010001297900004e00')
        result = self.parser.parse_nr_rrc_scell_info(header(c.LOG_5GNR_RRC_SERVING_CELL_INFO, payload), payload, dict())
        self.assertEqual(result['records'], [{
            'type': 'nr_serving_cell', 'pci': 669, 'dl_arfcn': 641760, 'ul_arfcn': 640726,
            'dl_bandwidth_mhz': 90, 'ul_bandwidth_mhz': 90, 'band': 78, 'cell_id': 0x4f27d1200,
            'mcc': '262', 'mnc': '01', 'tac': 0x7929,
        }])

    def test_mm_state(self):
        payload = binascii.unhexlify('0100000003000054f0800254f080a206001636ac480400a040fe')
        result = self.parser.parse_nr_mm_state(header(c.LOG_5GNR_NAS_5GMM_STATE, payload), payload, dict())
        self.assertEqual(result['records'], [{
            'type': 'nr_mm_state', 'mm_state': 3, 'mm_substate': 0, 'mm_update_status': 0,
            'mcc': '450', 'mnc': '08', 'tac': 0xa040fe,
        }])

    def test_nas_plain_uplink(self):
        # Version 1, NAS 15.2.0, Registration Request (EPD 0x7e, type 0x41)
        payload = binascii.unhexlify('01000000' + '0f0200' + '7e004179000d0100f110000000000000000010')
        result = self.parser.parse_nr_nas(header(c.LOG_5GNR_NAS_5GMM_PLAIN_OTA_OUTGOING_MESSAGE, payload), payload, dict(), 0xB80B)
        self.assertEqual(result['records'], [{
            'type': 'nr_nas', 'log_code': '0xb80b', 'direction': 'ul', 'plain': True,
            'message_type': 0x41, 'length': 19,
        }])


class TestJsonlWriter(unittest.TestCase):
    ts = datetime.datetime(2026, 11, 4, 12, 0, 0, 125000, tzinfo=datetime.timezone.utc)

    def lines(self, stream):
        return [json.loads(l) for l in stream.getvalue().splitlines()]

    def test_frames_and_records(self):
        out = io.StringIO()
        w = JsonlWriter(stream=out)
        w.write_cp(b'\x03\x00', 0, self.ts)
        w.write_up(b'\x45' * 20, 0, self.ts)
        w.write_record({'type': 'nr_mib', 'pci': 1}, 1, self.ts)
        cp, up, rec = self.lines(out)
        self.assertEqual(cp, {'kind': 'cp', 'radio_id': 0, 'frame': 1, 'data': '0300', 'ts': '2026-11-04T12:00:00.125000Z'})
        self.assertEqual(up, {'kind': 'up', 'radio_id': 0, 'frame': 2, 'length': 20, 'ts': '2026-11-04T12:00:00.125000Z'})
        self.assertEqual(rec, {'kind': 'record', 'radio_id': 1, 'last_frame': 2,
                               'record': {'type': 'nr_mib', 'pci': 1}, 'ts': '2026-11-04T12:00:00.125000Z'})

    def test_host_clock_is_flagged(self):
        out = io.StringIO()
        JsonlWriter(stream=out).write_cp(b'\x00', 0, datetime.datetime(2026, 11, 4, 12, 0, 0))
        self.assertEqual(self.lines(out)[0]['ts_basis'], 'host')

    def test_qualcomm_parser_forwards_records(self):
        out = io.StringIO()
        parser = QualcommParser()
        parser.set_writer([JsonlWriter(stream=out)])
        parser.postprocess_parse_result({'records': [{'type': 'nr_mib'}], 'ts': self.ts})
        self.assertEqual(self.lines(out)[0]['record'], {'type': 'nr_mib'})


if __name__ == '__main__':
    unittest.main()
