"""Financial cost models for traditional and blockchain freight payment systems."""

from dataclasses import dataclass
from typing import Dict, Optional, Any
import numpy as np


@dataclass
class PaymentFlowParams:
    annual_revenue: float = 17_700_000_000
    loads_per_year: int = 15_700_000
    dso_days: float = 49.0
    dpo_days: float = 27.0
    cost_of_capital: float = 0.07
    factoring_rate: float = 0.03
    fraud_loss_rate: float = 0.005
    admin_cost_per_load: float = 15.0
    days_in_year: int = 365

    def __post_init__(self):
        if self.annual_revenue <= 0:
            raise ValueError("annual_revenue must be positive")
        if self.loads_per_year <= 0:
            raise ValueError("loads_per_year must be positive")
        if self.dso_days < 0:
            raise ValueError("dso_days cannot be negative")
        if self.dpo_days < 0:
            raise ValueError("dpo_days cannot be negative")

    @property
    def daily_revenue(self) -> float:
        return self.annual_revenue / self.days_in_year

    @property
    def revenue_per_load(self) -> float:
        return self.annual_revenue / self.loads_per_year

    @property
    def working_capital_gap_days(self) -> float:
        return self.dso_days - self.dpo_days


class TraditionalPaymentModel:
    def __init__(self, params: PaymentFlowParams):
        self.params = params

    def calculate_working_capital_tied_up(self) -> float:
        gap_days = self.params.working_capital_gap_days
        return self.params.daily_revenue * gap_days

    def calculate_financing_cost(self) -> float:
        working_capital = self.calculate_working_capital_tied_up()
        return working_capital * self.params.cost_of_capital

    def calculate_factoring_cost(self, pct_factored: float = 0.30) -> float:
        return self.params.annual_revenue * pct_factored * self.params.factoring_rate

    def calculate_fraud_losses(self) -> float:
        return self.params.annual_revenue * self.params.fraud_loss_rate

    def calculate_admin_costs(self) -> float:
        return self.params.loads_per_year * self.params.admin_cost_per_load

    def total_payment_infrastructure_cost(self,
                                          pct_factored: float = 0.30,
                                          include_admin: bool = True) -> float:
        total = (
            self.calculate_financing_cost() +
            self.calculate_factoring_cost(pct_factored) +
            self.calculate_fraud_losses()
        )
        if include_admin:
            total += self.calculate_admin_costs()
        return total

    def get_cost_breakdown(self, pct_factored: float = 0.30) -> Dict[str, float]:
        return {
            'working_capital_tied_up': self.calculate_working_capital_tied_up(),
            'financing_cost': self.calculate_financing_cost(),
            'factoring_cost': self.calculate_factoring_cost(pct_factored),
            'fraud_losses': self.calculate_fraud_losses(),
            'admin_costs': self.calculate_admin_costs(),
            'total_cost': self.total_payment_infrastructure_cost(pct_factored)
        }


class BlockchainPaymentModel:
    def __init__(self,
                 params: PaymentFlowParams,
                 adoption_rate: float = 0.30,
                 tx_cost_per_load: float = 5.0,
                 new_dso_days: Optional[float] = None,
                 new_dpo_days: Optional[float] = None):
        self.params = params
        self.adoption_rate = adoption_rate
        self.tx_cost_per_load = tx_cost_per_load
        self.new_dso_days = new_dso_days if new_dso_days is not None else 0.5
        self.new_dpo_days = new_dpo_days if new_dpo_days is not None else 0.5

    def calculate_blended_working_capital_gap(self) -> float:
        traditional_gap = self.params.dso_days - self.params.dpo_days
        blockchain_gap = self.new_dso_days - self.new_dpo_days
        return (1 - self.adoption_rate) * traditional_gap + self.adoption_rate * blockchain_gap

    def calculate_reduced_working_capital(self) -> float:
        blended_gap = self.calculate_blended_working_capital_gap()
        return self.params.daily_revenue * blended_gap

    def calculate_working_capital_savings(self) -> float:
        traditional = TraditionalPaymentModel(self.params)
        traditional_wc = traditional.calculate_working_capital_tied_up()
        blockchain_wc = self.calculate_reduced_working_capital()
        return traditional_wc - blockchain_wc

    def calculate_financing_savings(self) -> float:
        wc_savings = self.calculate_working_capital_savings()
        return wc_savings * self.params.cost_of_capital

    def calculate_blockchain_tx_costs(self) -> float:
        blockchain_loads = int(self.params.loads_per_year * self.adoption_rate)
        return blockchain_loads * self.tx_cost_per_load

    def calculate_reduced_fraud(self, fraud_reduction_pct: float = 0.50) -> float:
        traditional = TraditionalPaymentModel(self.params)
        current_fraud = traditional.calculate_fraud_losses()
        effective_reduction = fraud_reduction_pct * self.adoption_rate
        return current_fraud * effective_reduction

    def calculate_factoring_savings(self, pct_factored: float = 0.30) -> float:
        traditional = TraditionalPaymentModel(self.params)
        current_factoring = traditional.calculate_factoring_cost(pct_factored)
        return current_factoring * self.adoption_rate

    def calculate_admin_savings(self) -> float:
        traditional = TraditionalPaymentModel(self.params)
        current_admin = traditional.calculate_admin_costs()
        return current_admin * self.adoption_rate * 0.70

    def total_cost(self) -> float:
        traditional = TraditionalPaymentModel(self.params)
        traditional_portion = (1 - self.adoption_rate)
        financing_cost = self.calculate_reduced_working_capital() * self.params.cost_of_capital
        factoring_cost = traditional.calculate_factoring_cost() * traditional_portion
        fraud_cost = traditional.calculate_fraud_losses() - self.calculate_reduced_fraud()
        admin_cost = traditional.calculate_admin_costs() - self.calculate_admin_savings()
        blockchain_cost = self.calculate_blockchain_tx_costs()
        return financing_cost + factoring_cost + fraud_cost + admin_cost + blockchain_cost

    def get_savings_breakdown(self, pct_factored: float = 0.30,
                              fraud_reduction_pct: float = 0.50) -> Dict[str, float]:
        return {
            'working_capital_reduction': self.calculate_working_capital_savings(),
            'financing_savings': self.calculate_financing_savings(),
            'factoring_savings': self.calculate_factoring_savings(pct_factored),
            'fraud_savings': self.calculate_reduced_fraud(fraud_reduction_pct),
            'admin_savings': self.calculate_admin_savings(),
            'blockchain_costs': self.calculate_blockchain_tx_costs(),
            'net_savings': self.calculate_net_savings(pct_factored, fraud_reduction_pct)
        }

    def calculate_net_savings(self, pct_factored: float = 0.30,
                               fraud_reduction_pct: float = 0.50) -> float:
        gross_savings = (
            self.calculate_financing_savings() +
            self.calculate_factoring_savings(pct_factored) +
            self.calculate_reduced_fraud(fraud_reduction_pct) +
            self.calculate_admin_savings()
        )
        costs = self.calculate_blockchain_tx_costs()
        return gross_savings - costs


def compare_models(traditional: TraditionalPaymentModel,
                   blockchain: BlockchainPaymentModel,
                   pct_factored: float = 0.30,
                   fraud_reduction_pct: float = 0.50) -> Dict[str, Any]:
    trad_breakdown = traditional.get_cost_breakdown(pct_factored)
    bc_breakdown = blockchain.get_savings_breakdown(pct_factored, fraud_reduction_pct)
    traditional_total = trad_breakdown['total_cost']
    blockchain_total = blockchain.total_cost()
    net_savings = traditional_total - blockchain_total

    return {
        'traditional': {'breakdown': trad_breakdown, 'total_cost': traditional_total},
        'blockchain': {'breakdown': bc_breakdown, 'total_cost': blockchain_total, 'adoption_rate': blockchain.adoption_rate},
        'comparison': {
            'net_savings': net_savings,
            'savings_pct': net_savings / traditional_total * 100 if traditional_total > 0 else 0,
            'roi': net_savings / blockchain.calculate_blockchain_tx_costs() if blockchain.calculate_blockchain_tx_costs() > 0 else float('inf')
        }
    }


def calculate_breakeven_adoption(params: PaymentFlowParams,
                                  tx_cost_per_load: float = 5.0,
                                  pct_factored: float = 0.30,
                                  fraud_reduction_pct: float = 0.50) -> float:
    low, high = 0.001, 1.0
    for _ in range(100):
        mid = (low + high) / 2
        blockchain = BlockchainPaymentModel(params, mid, tx_cost_per_load)
        savings = blockchain.calculate_net_savings(pct_factored, fraud_reduction_pct)
        if abs(savings) < 1000:
            return mid
        elif savings < 0:
            low = mid
        else:
            high = mid
    return mid


def sensitivity_to_adoption(params: PaymentFlowParams,
                             adoption_rates: Optional[list] = None,
                             tx_cost_per_load: float = 5.0) -> Dict[str, list]:
    if adoption_rates is None:
        adoption_rates = [i/10 for i in range(1, 11)]

    results = {
        'adoption_rate': adoption_rates,
        'net_savings': [],
        'financing_savings': [],
        'factoring_savings': [],
        'fraud_savings': [],
        'blockchain_costs': []
    }

    for rate in adoption_rates:
        blockchain = BlockchainPaymentModel(params, rate, tx_cost_per_load)
        results['net_savings'].append(blockchain.calculate_net_savings())
        results['financing_savings'].append(blockchain.calculate_financing_savings())
        results['factoring_savings'].append(blockchain.calculate_factoring_savings())
        results['fraud_savings'].append(blockchain.calculate_reduced_fraud())
        results['blockchain_costs'].append(blockchain.calculate_blockchain_tx_costs())

    return results
