"""
Unit tests for the cost model module.

Tests cover:
- PaymentFlowParams validation and calculations
- TraditionalPaymentModel cost calculations
- BlockchainPaymentModel savings calculations
- Model comparison functions
"""

import pytest
import numpy as np

from src.cost_model import (
    PaymentFlowParams,
    TraditionalPaymentModel,
    BlockchainPaymentModel,
    compare_models,
    calculate_breakeven_adoption,
    sensitivity_to_adoption,
)
from src.utils import calculate_dso, calculate_dpo, calculate_cash_conversion_cycle


class TestPaymentFlowParams:
    """Tests for PaymentFlowParams dataclass."""

    def test_default_initialization(self):
        """Test that default parameters are valid."""
        params = PaymentFlowParams()
        assert params.annual_revenue == 17_700_000_000
        assert params.loads_per_year == 15_700_000
        assert params.dso_days == 49.0
        assert params.dpo_days == 27.0
        assert params.cost_of_capital == 0.07

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        params = PaymentFlowParams(
            annual_revenue=10_000_000_000,
            loads_per_year=10_000_000,
            dso_days=45.0,
            dpo_days=25.0,
            cost_of_capital=0.06,
        )
        assert params.annual_revenue == 10_000_000_000
        assert params.loads_per_year == 10_000_000
        assert params.dso_days == 45.0

    def test_daily_revenue_property(self):
        """Test daily revenue calculation."""
        params = PaymentFlowParams(annual_revenue=365_000_000)
        assert params.daily_revenue == 1_000_000  # $365M / 365 days

    def test_revenue_per_load_property(self):
        """Test revenue per load calculation."""
        params = PaymentFlowParams(
            annual_revenue=100_000_000,
            loads_per_year=100_000,
        )
        assert params.revenue_per_load == 1_000  # $100M / 100K loads

    def test_working_capital_gap_property(self):
        """Test working capital gap calculation."""
        params = PaymentFlowParams(dso_days=50.0, dpo_days=20.0)
        assert params.working_capital_gap_days == 30.0

    def test_invalid_revenue_raises_error(self):
        """Test that negative revenue raises ValueError."""
        with pytest.raises(ValueError, match="annual_revenue must be positive"):
            PaymentFlowParams(annual_revenue=-1000)

    def test_invalid_loads_raises_error(self):
        """Test that negative loads raises ValueError."""
        with pytest.raises(ValueError, match="loads_per_year must be positive"):
            PaymentFlowParams(loads_per_year=0)

    def test_negative_dso_raises_error(self):
        """Test that negative DSO raises ValueError."""
        with pytest.raises(ValueError, match="dso_days cannot be negative"):
            PaymentFlowParams(dso_days=-5)


class TestTraditionalPaymentModel:
    """Tests for TraditionalPaymentModel class."""

    @pytest.fixture
    def params(self):
        """Create standard test parameters."""
        return PaymentFlowParams(
            annual_revenue=17_700_000_000,
            loads_per_year=15_700_000,
            dso_days=49.0,
            dpo_days=27.0,
            cost_of_capital=0.07,
            factoring_rate=0.03,
            fraud_loss_rate=0.005,
            admin_cost_per_load=15.0,
        )

    @pytest.fixture
    def model(self, params):
        """Create model with standard parameters."""
        return TraditionalPaymentModel(params)

    def test_working_capital_tied_up(self, model, params):
        """Test working capital calculation."""
        expected = params.daily_revenue * params.working_capital_gap_days
        actual = model.calculate_working_capital_tied_up()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_financing_cost(self, model, params):
        """Test financing cost calculation."""
        working_capital = model.calculate_working_capital_tied_up()
        expected = working_capital * params.cost_of_capital
        actual = model.calculate_financing_cost()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_factoring_cost(self, model, params):
        """Test factoring cost calculation."""
        pct_factored = 0.30
        expected = params.annual_revenue * pct_factored * params.factoring_rate
        actual = model.calculate_factoring_cost(pct_factored)
        assert actual == pytest.approx(expected, rel=0.01)

    def test_fraud_losses(self, model, params):
        """Test fraud loss calculation."""
        expected = params.annual_revenue * params.fraud_loss_rate
        actual = model.calculate_fraud_losses()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_admin_costs(self, model, params):
        """Test administrative cost calculation."""
        expected = params.loads_per_year * params.admin_cost_per_load
        actual = model.calculate_admin_costs()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_total_cost(self, model):
        """Test total cost is sum of components."""
        total = model.total_payment_infrastructure_cost()
        expected = (
            model.calculate_financing_cost() +
            model.calculate_factoring_cost() +
            model.calculate_fraud_losses() +
            model.calculate_admin_costs()
        )
        assert total == pytest.approx(expected, rel=0.01)

    def test_cost_breakdown_keys(self, model):
        """Test cost breakdown returns all expected keys."""
        breakdown = model.get_cost_breakdown()
        expected_keys = {
            'working_capital_tied_up',
            'financing_cost',
            'factoring_cost',
            'fraud_losses',
            'admin_costs',
            'total_cost',
        }
        assert set(breakdown.keys()) == expected_keys


class TestBlockchainPaymentModel:
    """Tests for BlockchainPaymentModel class."""

    @pytest.fixture
    def params(self):
        """Create standard test parameters."""
        return PaymentFlowParams(
            annual_revenue=17_700_000_000,
            loads_per_year=15_700_000,
            dso_days=49.0,
            dpo_days=27.0,
            cost_of_capital=0.07,
            factoring_rate=0.03,
            fraud_loss_rate=0.005,
        )

    @pytest.fixture
    def model(self, params):
        """Create blockchain model with 30% adoption."""
        return BlockchainPaymentModel(params, adoption_rate=0.30, tx_cost_per_load=5.0)

    def test_blended_working_capital_gap(self, model, params):
        """Test blended working capital gap calculation."""
        traditional_gap = params.dso_days - params.dpo_days
        blockchain_gap = 0.5 - 0.5  # Default new DSO/DPO
        expected = 0.70 * traditional_gap + 0.30 * blockchain_gap
        actual = model.calculate_blended_working_capital_gap()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_working_capital_reduction(self, model, params):
        """Test working capital is reduced with blockchain adoption."""
        traditional = TraditionalPaymentModel(params)
        traditional_wc = traditional.calculate_working_capital_tied_up()
        blockchain_wc = model.calculate_reduced_working_capital()
        assert blockchain_wc < traditional_wc

    def test_financing_savings_positive(self, model):
        """Test financing savings are positive."""
        savings = model.calculate_financing_savings()
        assert savings > 0

    def test_blockchain_tx_costs(self, model, params):
        """Test blockchain transaction cost calculation."""
        expected = int(params.loads_per_year * 0.30) * 5.0
        actual = model.calculate_blockchain_tx_costs()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_fraud_reduction(self, model, params):
        """Test fraud reduction calculation."""
        traditional = TraditionalPaymentModel(params)
        current_fraud = traditional.calculate_fraud_losses()
        fraud_savings = model.calculate_reduced_fraud(fraud_reduction_pct=0.50)
        # At 30% adoption, 50% fraud reduction => 15% effective reduction
        expected = current_fraud * 0.30 * 0.50
        assert fraud_savings == pytest.approx(expected, rel=0.01)

    def test_factoring_savings(self, model, params):
        """Test factoring savings calculation."""
        traditional = TraditionalPaymentModel(params)
        current_factoring = traditional.calculate_factoring_cost()
        # At 30% adoption, factoring is eliminated for blockchain loads
        expected = current_factoring * 0.30
        actual = model.calculate_factoring_savings()
        assert actual == pytest.approx(expected, rel=0.01)

    def test_net_savings_positive(self, model):
        """Test net savings are positive at 30% adoption."""
        net_savings = model.calculate_net_savings()
        assert net_savings > 0

    def test_higher_adoption_higher_savings(self, params):
        """Test that higher adoption rates lead to higher savings."""
        model_30 = BlockchainPaymentModel(params, adoption_rate=0.30)
        model_50 = BlockchainPaymentModel(params, adoption_rate=0.50)
        assert model_50.calculate_net_savings() > model_30.calculate_net_savings()

    def test_savings_breakdown_keys(self, model):
        """Test savings breakdown returns all expected keys."""
        breakdown = model.get_savings_breakdown()
        expected_keys = {
            'working_capital_reduction',
            'financing_savings',
            'factoring_savings',
            'fraud_savings',
            'admin_savings',
            'blockchain_costs',
            'net_savings',
        }
        assert set(breakdown.keys()) == expected_keys


class TestCompareModels:
    """Tests for model comparison function."""

    @pytest.fixture
    def models(self):
        """Create traditional and blockchain models."""
        params = PaymentFlowParams()
        traditional = TraditionalPaymentModel(params)
        blockchain = BlockchainPaymentModel(params, adoption_rate=0.30)
        return traditional, blockchain

    def test_comparison_structure(self, models):
        """Test comparison returns expected structure."""
        traditional, blockchain = models
        result = compare_models(traditional, blockchain)
        assert 'traditional' in result
        assert 'blockchain' in result
        assert 'comparison' in result

    def test_net_savings_positive(self, models):
        """Test net savings in comparison are positive."""
        traditional, blockchain = models
        result = compare_models(traditional, blockchain)
        assert result['comparison']['net_savings'] > 0

    def test_savings_percentage_reasonable(self, models):
        """Test savings percentage is in reasonable range."""
        traditional, blockchain = models
        result = compare_models(traditional, blockchain)
        # Savings should be between 0% and 50% of traditional costs
        assert 0 < result['comparison']['savings_pct'] < 50


class TestUtilityFunctions:
    """Tests for utility calculation functions."""

    def test_dso_calculation(self):
        """Test DSO calculation formula."""
        # DSO = (A/R / Revenue) * 365
        dso = calculate_dso(2380, 17700, 365)
        assert dso == pytest.approx(49.07, rel=0.01)

    def test_dpo_calculation(self):
        """Test DPO calculation formula."""
        # DPO = (A/P / COGS) * 365
        dpo = calculate_dpo(1089, 14930, 365)
        assert dpo == pytest.approx(26.62, rel=0.01)

    def test_cash_conversion_cycle(self):
        """Test CCC calculation."""
        ccc = calculate_cash_conversion_cycle(49, 27, dio=0)
        assert ccc == 22

    def test_dso_zero_revenue_raises(self):
        """Test DSO calculation raises error for zero revenue."""
        with pytest.raises(ValueError, match="Revenue must be positive"):
            calculate_dso(100, 0)

    def test_dpo_zero_cogs_raises(self):
        """Test DPO calculation raises error for zero COGS."""
        with pytest.raises(ValueError, match="COGS must be positive"):
            calculate_dpo(100, 0)


class TestBreakevenAndSensitivity:
    """Tests for breakeven and sensitivity analysis functions."""

    @pytest.fixture
    def params(self):
        """Create standard test parameters."""
        return PaymentFlowParams()

    def test_breakeven_adoption_in_range(self, params):
        """Test breakeven adoption rate is between 0 and 1."""
        breakeven = calculate_breakeven_adoption(params)
        assert 0 < breakeven < 1

    def test_sensitivity_to_adoption_structure(self, params):
        """Test sensitivity analysis returns expected structure."""
        results = sensitivity_to_adoption(params)
        expected_keys = {
            'adoption_rate',
            'net_savings',
            'financing_savings',
            'factoring_savings',
            'fraud_savings',
            'blockchain_costs',
        }
        assert set(results.keys()) == expected_keys

    def test_sensitivity_monotonic_savings(self, params):
        """Test that savings increase monotonically with adoption."""
        results = sensitivity_to_adoption(params)
        for i in range(1, len(results['net_savings'])):
            assert results['net_savings'][i] > results['net_savings'][i-1]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
