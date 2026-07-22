"""Tests for the QGIS-independent CzechRad parser and validator."""

import unittest
from datetime import date, timezone
from pathlib import Path

from czechrad_studio.core import LocationQuality, TimeQuality
from czechrad_studio.importer import (
    CzechRadParseError,
    calculate_checksum,
    parse_log,
    parse_measurement_line,
    validate_measurement,
)


FIXTURE = Path(__file__).parent / "fixtures" / "czechrad_sample.log"


class CzechRadParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = parse_log(FIXTURE.read_text(encoding="utf-8").splitlines())

    def test_parses_measurements_and_skips_headers(self):
        self.assertEqual(5, len(self.parsed.measurements))
        self.assertEqual(0, len(self.parsed.failures))
        self.assertEqual(4, self.parsed.measurements[0].line_number)

    def test_valid_gps_record_has_geometry(self):
        measurement = self.parsed.measurements[0]
        validation = validate_measurement(
            measurement, expected_date=date(2026, 7, 17)
        )

        self.assertTrue(measurement.checksum_valid)
        self.assertEqual(timezone.utc, measurement.timestamp.tzinfo)
        self.assertAlmostEqual(50.0, measurement.latitude)
        self.assertAlmostEqual(14.0, measurement.longitude)
        self.assertEqual(LocationQuality.VALID, validation.location_quality)
        self.assertTrue(validation.has_geometry)
        self.assertTrue(validation.usable_without_location)

    def test_nogps_record_keeps_radiation_without_geometry(self):
        validation = validate_measurement(
            self.parsed.measurements[1], expected_date=date(2026, 7, 17)
        )

        self.assertEqual(LocationQuality.NONE, validation.location_quality)
        self.assertFalse(validation.has_geometry)
        self.assertTrue(validation.usable_without_location)
        self.assertIn("missing_coordinates", validation.issues)

    def test_a_status_is_not_enough_for_a_trusted_position(self):
        validation = validate_measurement(
            self.parsed.measurements[2], expected_date=date(2026, 7, 17)
        )

        self.assertEqual(LocationQuality.INVALID, validation.location_quality)
        self.assertFalse(validation.has_geometry)
        self.assertIn("untrusted_gps_fix", validation.issues)

    def test_radiation_status_is_independent_from_gps_status(self):
        payload = (
            "CZRA1,TEST,2026-07-17T15:08:42Z,0,4,4,V,"
            "5000.0000,N,01400.0000,E,250.00,A,8,100"
        )
        measurement = parse_measurement_line(
            f"${payload}*{calculate_checksum(payload):X}"
        )
        validation = validate_measurement(
            measurement, expected_date=date(2026, 7, 17)
        )

        self.assertEqual("V", measurement.radiation_status)
        self.assertEqual("A", measurement.gps_status)
        self.assertTrue(validation.has_geometry)

    def test_distinguishes_supported_device_sentence_types(self):
        for device_type, family in (
            ("CZRA1", "CzechRad"),
            ("CZRDD", "CzechRad (starší formát)"),
            ("BNRDD", "Safecast bGeigie Nano"),
        ):
            payload = (
                f"{device_type},TEST,2026-07-17T15:08:42Z,40,4,100,A,"
                "5000.0000,N,01400.0000,E,250.00,A,8,100"
            )
            measurement = parse_measurement_line(
                f"${payload}*{calculate_checksum(payload):X}"
            )
            self.assertEqual(device_type, measurement.device_type)
            self.assertEqual(family, measurement.device_family)

    def test_rejects_unknown_future_device_type_explicitly(self):
        payload = (
            "CZRA2,TEST,2026-07-17T15:08:42Z,40,4,100,A,"
            "5000.0000,N,01400.0000,E,250.00,A,8,100"
        )
        with self.assertRaisesRegex(CzechRadParseError, "unsupported"):
            parse_measurement_line(
                f"${payload}*{calculate_checksum(payload):X}"
            )

    def test_invalid_coordinate_text_keeps_radiation_without_geometry(self):
        line = (
            "$CZRA1,0796,2026-07-21T03:03:34Z,27,5,23,V,"
            "6027.4121,N,-04210.9048,W,16107.92,A,0,9999*39"
        )
        measurement = parse_measurement_line(line)
        validation = validate_measurement(
            measurement, expected_date=date(2026, 7, 21)
        )

        self.assertTrue(measurement.checksum_valid)
        self.assertIsNone(measurement.latitude)
        self.assertIsNone(measurement.longitude)
        self.assertIsNotNone(measurement.coordinate_issue)
        self.assertFalse(validation.has_geometry)
        self.assertTrue(validation.usable_without_location)
        self.assertIn("invalid_coordinate_encoding", validation.issues)

    def test_device_default_date_is_untrusted(self):
        validation = validate_measurement(
            self.parsed.measurements[3], expected_date=date(2026, 7, 17)
        )

        self.assertEqual(TimeQuality.UNTRUSTED, validation.time_quality)
        self.assertFalse(validation.usable_without_location)
        self.assertIn("timestamp_date_mismatch", validation.issues)

    def test_checksum_mismatch_is_reported_by_validation(self):
        original = self.parsed.measurements[0].raw_line
        damaged = parse_measurement_line(original[:-2] + "00")
        validation = validate_measurement(
            damaged, expected_date=date(2026, 7, 17)
        )

        self.assertFalse(damaged.checksum_valid)
        self.assertFalse(validation.usable_without_location)
        self.assertIn("checksum_mismatch", validation.issues)

    def test_accepts_single_digit_checksum_written_by_device(self):
        measurement = self.parsed.measurements[1]

        self.assertEqual(0x0E, measurement.expected_checksum)
        self.assertTrue(measurement.checksum_valid)

    def test_structural_error_is_audited_without_stopping_log(self):
        parsed = parse_log(["# header", "$CZRA1,broken"])

        self.assertEqual(0, len(parsed.measurements))
        self.assertEqual(1, len(parsed.failures))
        self.assertEqual(2, parsed.failures[0].line_number)

    def test_non_measurement_line_is_rejected(self):
        with self.assertRaises(CzechRadParseError):
            parse_measurement_line("not a measurement")


if __name__ == "__main__":
    unittest.main()
