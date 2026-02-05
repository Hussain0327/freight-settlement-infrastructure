"""
Unit tests for the working capital simulation module.

Tests cover:
- SimulationParams configuration
- WorkingCapitalSimulator core functionality
- Risk metric calculations (VaR, CVaR)
- Comparative simulations
"""

import pytest
import numpy as np

from src.working_capital import (
    SimulationParams,
    SimulationResults,
    WorkingCapitalSimulator,
    calculate_risk_reduction,
)


class TestSimulationParams:
    """Tests for SimulationParams dataclass."""

    def test_default_initialization(self):
        """Test that default parameters are valid."""
        params = SimulationParams()
        assert params.n_simulations == 10_000
        assert params.simulation_days == 365
        assert params.loads_per_day == 43_014
        assert params.shipper_payment_mean == 49.0
        assert params.carrier_payment_mean == 27.0

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        params = SimulationParams(
            n_simulations=1_000,
            simulation_days=180,
            loads_per_day=50_000,
            random_seed=123,
        )
        assert params.n_simulations == 1_000
        assert params.simulation_days == 180
        assert params.loads_per_day == 50_000
        assert params.random_seed == 123

    def test_random_seed_sets_state(self):
        """Test that random seed provides reproducibility."""
        params1 = SimulationParams(n_simulations=100, random_seed=42)
        random1 = np.random.random(10).copy()

        params2 = SimulationParams(n_simulations=100, random_seed=42)
        random2 = np.random.random(10)

        np.testing.assert_array_almost_equal(random1, random2)


class TestSimulationResults:
    """Tests for SimulationResults dataclass."""

    @pytest.fixture
    def sample_results(self):
        """Create sample simulation results."""
        n_sims = 100
        n_days = 30
        positions = np.random.randn(n_sims, n_days) * 1_000_000 + 10_000_000

        return SimulationResults(
            daily_positions=positions,
            mean_position=np.mean(positions, axis=0),
            std_position=np.std(positions, axis=0),
            var_95=np.percentile(np.max(positions, axis=1), 95),
            var_99=np.percentile(np.max(positions, axis=1), 99),
            cvar_95=np.mean(np.max(positions, axis=1)[np.max(positions, axis=1) >= np.percentile(np.max(positions, axis=1), 95)]),
            max_drawdown=1_000_000,
            peak_capital_required=15_000_000,
        )

    def test_summary_keys(self, sample_results):
        """Test summary returns expected keys."""
        summary = sample_results.summary()
        expected_keys = {
            'mean_daily_position',
            'std_daily_position',
            'var_95',
            'var_99',
            'cvar_95',
            'max_drawdown',
            'peak_capital_required',
        }
        assert set(summary.keys()) == expected_keys

    def test_summary_values_numeric(self, sample_results):
        """Test summary values are numeric."""
        summary = sample_results.summary()
        for key, value in summary.items():
            assert isinstance(value, (int, float))


class TestWorkingCapitalSimulator:
    """Tests for WorkingCapitalSimulator class."""

    @pytest.fixture
    def small_params(self):
        """Create small parameters for faster tests."""
        return SimulationParams(
            n_simulations=100,
            simulation_days=30,
            loads_per_day=1_000,
            random_seed=42,
        )

    @pytest.fixture
    def simulator(self, small_params):
        """Create simulator with small parameters."""
        return WorkingCapitalSimulator(small_params)

    def test_traditional_simulation_shape(self, simulator, small_params):
        """Test traditional simulation output shape."""
        positions = simulator.simulate_traditional_fast()
        assert positions.shape == (small_params.n_simulations, small_params.simulation_days)

    def test_blockchain_simulation_shape(self, simulator, small_params):
        """Test blockchain simulation output shape."""
        positions = simulator.simulate_blockchain(adoption_rate=0.30)
        assert positions.shape == (small_params.n_simulations, small_params.simulation_days)

    def test_blockchain_reduces_positions(self, simulator):
        """Test that blockchain adoption reduces working capital positions."""
        trad_positions = simulator.simulate_traditional_fast()
        bc_positions = simulator.simulate_blockchain(adoption_rate=0.50)

        # Average positions should be lower with blockchain
        trad_mean = np.mean(np.max(trad_positions, axis=1))
        bc_mean = np.mean(np.max(bc_positions, axis=1))
        assert bc_mean < trad_mean

    def test_var_calculation_positive(self, simulator):
        """Test VaR calculation returns positive value."""
        positions = simulator.simulate_traditional_fast()
        var_95 = simulator.calculate_var(positions, confidence=0.95)
        assert var_95 > 0

    def test_var_99_greater_than_95(self, simulator):
        """Test VaR at 99% is greater than VaR at 95%."""
        positions = simulator.simulate_traditional_fast()
        var_95 = simulator.calculate_var(positions, confidence=0.95)
        var_99 = simulator.calculate_var(positions, confidence=0.99)
        assert var_99 >= var_95

    def test_expected_shortfall_greater_than_var(self, simulator):
        """Test Expected Shortfall >= VaR."""
        positions = simulator.simulate_traditional_fast()
        var_95 = simulator.calculate_var(positions, confidence=0.95)
        es_95 = simulator.calculate_expected_shortfall(positions, confidence=0.95)
        assert es_95 >= var_95

    def test_monte_carlo_returns_results(self, simulator):
        """Test run_monte_carlo returns SimulationResults."""
        results = simulator.run_monte_carlo(use_fast=True)
        assert isinstance(results, SimulationResults)

    def test_monte_carlo_results_valid(self, simulator):
        """Test Monte Carlo results have valid values."""
        results = simulator.run_monte_carlo(use_fast=True)
        assert results.var_95 > 0
        assert results.cvar_95 >= results.var_95
        assert results.peak_capital_required > 0

    def test_comparative_simulation_keys(self, simulator):
        """Test comparative simulation returns expected adoption rates."""
        adoption_rates = [0.0, 0.30, 0.50]
        results = simulator.run_comparative_simulation(adoption_rates)
        expected_keys = {'0%', '30%', '50%'}
        assert set(results.keys()) == expected_keys

    def test_comparative_simulation_decreasing_risk(self, simulator):
        """Test that higher adoption reduces VaR."""
        adoption_rates = [0.0, 0.30, 0.50, 1.0]
        results = simulator.run_comparative_simulation(adoption_rates)

        vars = [results[f'{r:.0%}'].var_95 for r in adoption_rates]
        # VaR should generally decrease with higher adoption
        # Allow some noise but overall trend should be downward
        assert vars[0] > vars[-1]


class TestRiskReduction:
    """Tests for risk reduction calculation function."""

    @pytest.fixture
    def results_pair(self):
        """Create pair of simulation results for comparison."""
        n_sims = 100
        n_days = 30

        # Traditional results (higher risk)
        trad_positions = np.random.randn(n_sims, n_days) * 2_000_000 + 20_000_000
        traditional = SimulationResults(
            daily_positions=trad_positions,
            mean_position=np.mean(trad_positions, axis=0),
            std_position=np.std(trad_positions, axis=0),
            var_95=25_000_000,
            var_99=28_000_000,
            cvar_95=27_000_000,
            max_drawdown=3_000_000,
            peak_capital_required=30_000_000,
        )

        # Blockchain results (lower risk)
        bc_positions = np.random.randn(n_sims, n_days) * 1_000_000 + 15_000_000
        blockchain = SimulationResults(
            daily_positions=bc_positions,
            mean_position=np.mean(bc_positions, axis=0),
            std_position=np.std(bc_positions, axis=0),
            var_95=18_000_000,
            var_99=20_000_000,
            cvar_95=19_000_000,
            max_drawdown=2_000_000,
            peak_capital_required=22_000_000,
        )

        return traditional, blockchain

    def test_risk_reduction_keys(self, results_pair):
        """Test risk reduction returns expected keys."""
        traditional, blockchain = results_pair
        reduction = calculate_risk_reduction(traditional, blockchain)
        expected_keys = {
            'var_95_reduction',
            'var_95_reduction_pct',
            'cvar_95_reduction',
            'peak_capital_reduction',
            'volatility_reduction',
        }
        assert set(reduction.keys()) == expected_keys

    def test_risk_reduction_positive(self, results_pair):
        """Test risk reduction values are positive (blockchain reduces risk)."""
        traditional, blockchain = results_pair
        reduction = calculate_risk_reduction(traditional, blockchain)
        assert reduction['var_95_reduction'] > 0
        assert reduction['var_95_reduction_pct'] > 0
        assert reduction['cvar_95_reduction'] > 0
        assert reduction['peak_capital_reduction'] > 0

    def test_risk_reduction_percentage_valid(self, results_pair):
        """Test risk reduction percentage is in valid range."""
        traditional, blockchain = results_pair
        reduction = calculate_risk_reduction(traditional, blockchain)
        assert 0 < reduction['var_95_reduction_pct'] < 100


class TestReproducibility:
    """Tests for simulation reproducibility."""

    def test_same_seed_same_results(self):
        """Test that same seed produces same results."""
        params1 = SimulationParams(n_simulations=100, simulation_days=30, random_seed=42)
        sim1 = WorkingCapitalSimulator(params1)
        results1 = sim1.run_monte_carlo(use_fast=True)

        params2 = SimulationParams(n_simulations=100, simulation_days=30, random_seed=42)
        sim2 = WorkingCapitalSimulator(params2)
        results2 = sim2.run_monte_carlo(use_fast=True)

        assert results1.var_95 == pytest.approx(results2.var_95, rel=0.01)

    def test_different_seed_different_results(self):
        """Test that different seeds produce different results."""
        params1 = SimulationParams(n_simulations=100, simulation_days=30, random_seed=42)
        sim1 = WorkingCapitalSimulator(params1)
        results1 = sim1.run_monte_carlo(use_fast=True)

        params2 = SimulationParams(n_simulations=100, simulation_days=30, random_seed=99)
        sim2 = WorkingCapitalSimulator(params2)
        results2 = sim2.run_monte_carlo(use_fast=True)

        # Results should be different (with very high probability)
        assert results1.var_95 != results2.var_95


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
