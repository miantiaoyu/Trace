import unittest

from trace_api_probe.carriers import Carrier, normalize_carrier, parse_carrier


class CarrierTests(unittest.TestCase):
    def test_normalize_maersk_aliases(self) -> None:
        self.assertEqual(normalize_carrier("MSK 马士基"), Carrier.MAERSK)
        self.assertEqual(normalize_carrier("MSK马士基"), Carrier.MAERSK)
        self.assertEqual(normalize_carrier("MSK 马士基 NVO"), Carrier.MAERSK)

    def test_normalize_cma_and_msc_aliases(self) -> None:
        self.assertEqual(normalize_carrier("CMA 达飞"), Carrier.CMA_CGM)
        self.assertEqual(normalize_carrier("MSC 地中海"), Carrier.MSC)

    def test_normalize_hmm_prefix_with_mojibake_suffix(self) -> None:
        self.assertEqual(normalize_carrier("HMM ş«ĐÂ BCO"), Carrier.HMM)

    def test_parse_carrier_rejects_unknown_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "不支持的船司"):
            parse_carrier("不存在的船司")


if __name__ == "__main__":
    unittest.main()
