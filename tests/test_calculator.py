import unittest

from dosimetry_app.calculator import compute_p_ion_two_voltage, compute_p_pol, compute_p_tp
from dosimetry_app.formulas import safe_eval_formula


class CalculatorTests(unittest.TestCase):
    def test_compute_p_tp_hartmann_like(self):
        value = compute_p_tp(t_meas_c=20.6, p_meas_kpa=98.18, t0_c=20.0, p0_kpa=101.325)
        self.assertAlmostEqual(value, 1.034145, places=6)

    def test_compute_p_ion_two_voltage(self):
        value = compute_p_ion_two_voltage(m_high=7.674, m_low=7.630, v_high=300, v_low=150)
        self.assertGreater(value, 1.0)

    def test_compute_p_pol(self):
        value = compute_p_pol(m_pos=7.674, m_neg=7.660, m_ref=7.674)
        self.assertAlmostEqual(value, 0.9991, places=3)

    def test_safe_eval_formula(self):
        output = safe_eval_formula("M_Q * N_Dw_60Co * k_Q", {"M_Q": 1e-8, "N_Dw_60Co": 5.233e7, "k_Q": 0.973})
        self.assertAlmostEqual(output, 0.5091709, places=6)


if __name__ == "__main__":
    unittest.main()
