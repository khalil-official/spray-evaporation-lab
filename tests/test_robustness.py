"""Robustness and physical-invariant tests for EvapModel.run().

Covers the loop guards fixed in model.py:
- a NaN state must stop the run instead of comparing false forever
  (``d_d == np.nan`` is never true);
- the complex-value warning must not raise ``TypeError`` by subscripting
  the pydantic model (``self.model['modelling']``);
plus physical invariants of the reference water-in-argon case.
"""
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from dropletevapmodel import DropletEvapModel, EvapModel, load_config


def build_evap_model(max_iteration=None):
    config = load_config('tests/assets/config.yml')
    config['gas_properties'] = pd.read_csv(
        'tests/assets/gas.csv', index_col='property')['Ar'].to_dict()
    config['fluid_properties'] = pd.read_csv(
        'tests/assets/liq.csv', index_col='property')['H2O'].to_dict()
    if max_iteration is not None:
        config['simulation_config']['modelling']['max_iteration'] = max_iteration
    return EvapModel(DropletEvapModel(**config))


class TestRunGuards(unittest.TestCase):

    def test_nan_state_stops_run(self):
        evap_model = build_evap_model(max_iteration=500)
        real_evaluate = evap_model.evaluate_state

        def poison(res_prec, *args, **kwargs):
            state = real_evaluate(res_prec, *args, **kwargs)
            state['d_d'] = np.nan
            return state

        evap_model.evaluate_state = poison
        with self.assertLogs('modelling_droplet_evaporation', level='INFO'):
            result = evap_model.run()
        self.assertTrue(np.isnan(result[max(result.keys())]['d_d']))
        self.assertLessEqual(max(result.keys()), 1,
                             'run() must stop at the first non-finite state')

    def test_inf_state_stops_run(self):
        evap_model = build_evap_model(max_iteration=500)
        real_evaluate = evap_model.evaluate_state

        def poison(res_prec, *args, **kwargs):
            state = real_evaluate(res_prec, *args, **kwargs)
            state['t_d'] = np.inf
            return state

        evap_model.evaluate_state = poison
        result = evap_model.run()
        self.assertFalse(np.isfinite(result[max(result.keys())]['t_d']))
        self.assertLessEqual(max(result.keys()), 1)

    def test_complex_value_logs_without_raising(self):
        evap_model = build_evap_model(max_iteration=5)
        real_evaluate = evap_model.evaluate_state
        calls = {'count': 0}

        def poison(res_prec, *args, **kwargs):
            state = real_evaluate(res_prec, *args, **kwargs)
            calls['count'] += 1
            if calls['count'] == 1:
                # chi_vg is recomputed from pvap_g each step, so poisoning it
                # only exercises the complex-value reporting path.
                state['chi_vg'] = complex(0.01, 0.0)
            return state

        evap_model.evaluate_state = poison
        with self.assertLogs('modelling_droplet_evaporation', level='WARNING') as logs:
            result = evap_model.run()
        self.assertTrue(any('complex' in message for message in logs.output))
        self.assertGreater(max(result.keys()), 1)


class TestPhysicalInvariants(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.evap_model = build_evap_model()
        cls.result = cls.evap_model.run()

    def accepted_steps(self):
        # The final stored state is the one that triggered the stop condition
        # (non-positive or non-finite diameter/temperature) and can lie
        # outside the physical range by construction.
        return sorted(self.result)[:-1]

    def test_terminal_state_triggers_stop_condition(self):
        terminal = self.result[max(self.result)]
        self.assertTrue(
            terminal['d_d'] <= 0 or terminal['t_d'] <= 0
            or not np.isfinite(terminal['d_d']) or not np.isfinite(terminal['t_d']))

    def test_diameter_shrinks_overall_until_evaporation(self):
        steps = sorted(self.result)
        diameters = [self.result[t]['d_d'] for t in steps]
        self.assertGreater(diameters[0], 0.0)
        self.assertLess(diameters[-1], diameters[0])
        # The droplet never grows beyond its initial size at any step.
        self.assertLessEqual(max(diameters[:-1]), diameters[0])

    def test_gas_humidity_rises_overall(self):
        ppm = [self.result[t]['ppm'] for t in sorted(self.result)]
        self.assertGreater(ppm[-1], ppm[0])
        for earlier, later in zip(ppm, ppm[1:]):
            self.assertGreaterEqual(later, earlier - 0.01)

    def test_droplet_temperature_stays_physical(self):
        boiling_t = self.evap_model.model.fluid_properties.boiling_t
        for t in self.accepted_steps():
            t_d = self.result[t]['t_d']
            self.assertTrue(np.isfinite(t_d))
            self.assertGreater(t_d, 0.0)
            self.assertLess(t_d, boiling_t)

    def test_evaporation_time_regression(self):
        steps = sorted(self.result)
        final_time = self.result[steps[-1]]['time']
        self.assertAlmostEqual(final_time, 0.9992800, delta=1e-6)


if __name__ == '__main__':
    unittest.main()
