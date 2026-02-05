from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

from .cost_model import PaymentFlowParams, TraditionalPaymentModel, BlockchainPaymentModel


@dataclass
class AdoptionScenario:
    name: str
    adoption_rate: float
    shipper_escrow_pct: float = 0.40
    carrier_tech_ready_pct: float = 0.70
    tx_cost_per_load: float = 5.0
    fraud_reduction_pct: float = 0.15
    regulatory_approval: bool = True
    implementation_cost: float = 50_000_000  # $50M default
    annual_maintenance_cost: float = 10_000_000  # $10M default

    def __post_init__(self):
        if not 0 <= self.adoption_rate <= 1:
            raise ValueError("adoption_rate must be between 0 and 1")
        if not 0 <= self.shipper_escrow_pct <= 1:
            raise ValueError("shipper_escrow_pct must be between 0 and 1")
        if not 0 <= self.carrier_tech_ready_pct <= 1:
            raise ValueError("carrier_tech_ready_pct must be between 0 and 1")
        if self.tx_cost_per_load < 0:
            raise ValueError("tx_cost_per_load cannot be negative")

    @property
    def effective_adoption(self) -> float:
        return min(
            self.adoption_rate,
            self.shipper_escrow_pct,
            self.carrier_tech_ready_pct
        )


# Predefined scenarios based on industry analysis
SCENARIOS: Dict[str, AdoptionScenario] = {
    'conservative': AdoptionScenario(
        name='Conservative',
        adoption_rate=0.10,
        shipper_escrow_pct=0.20,
        carrier_tech_ready_pct=0.50,
        tx_cost_per_load=10.0,
        fraud_reduction_pct=0.05,
        regulatory_approval=False,
        implementation_cost=75_000_000,
        annual_maintenance_cost=15_000_000
    ),
    'base_case': AdoptionScenario(
        name='Base Case',
        adoption_rate=0.30,
        shipper_escrow_pct=0.40,
        carrier_tech_ready_pct=0.70,
        tx_cost_per_load=5.0,
        fraud_reduction_pct=0.15,
        regulatory_approval=True,
        implementation_cost=50_000_000,
        annual_maintenance_cost=10_000_000
    ),
    'optimistic': AdoptionScenario(
        name='Optimistic',
        adoption_rate=0.50,
        shipper_escrow_pct=0.60,
        carrier_tech_ready_pct=0.85,
        tx_cost_per_load=3.0,
        fraud_reduction_pct=0.25,
        regulatory_approval=True,
        implementation_cost=40_000_000,
        annual_maintenance_cost=8_000_000
    ),
    'aggressive': AdoptionScenario(
        name='Aggressive',
        adoption_rate=0.75,
        shipper_escrow_pct=0.80,
        carrier_tech_ready_pct=0.95,
        tx_cost_per_load=2.0,
        fraud_reduction_pct=0.40,
        regulatory_approval=True,
        implementation_cost=35_000_000,
        annual_maintenance_cost=7_000_000
    ),
}


@dataclass
class ScenarioResults:
    scenario: AdoptionScenario
    traditional_cost: float
    blockchain_cost: float
    net_savings: float
    roi: float
    payback_years: float
    npv_5yr: float
    savings_breakdown: Dict[str, float]


def run_scenario_analysis(params: PaymentFlowParams,
                           scenario: AdoptionScenario,
                           discount_rate: float = 0.10,
                           analysis_years: int = 5) -> ScenarioResults:

    # Create models
    traditional = TraditionalPaymentModel(params)
    blockchain = BlockchainPaymentModel(
        params,
        adoption_rate=scenario.effective_adoption,
        tx_cost_per_load=scenario.tx_cost_per_load
    )

    # Calculate costs
    traditional_cost = traditional.total_payment_infrastructure_cost()

    # Blockchain net savings
    net_savings = blockchain.calculate_net_savings(
        fraud_reduction_pct=scenario.fraud_reduction_pct
    )

    # Subtract maintenance cost
    net_annual_savings = net_savings - scenario.annual_maintenance_cost

    # Total blockchain cost (traditional cost minus savings plus maintenance)
    blockchain_cost = traditional_cost - net_savings + scenario.annual_maintenance_cost

    # ROI calculation
    total_implementation = scenario.implementation_cost
    if total_implementation > 0:
        roi = net_annual_savings / total_implementation
        payback_years = total_implementation / net_annual_savings if net_annual_savings > 0 else float('inf')
    else:
        roi = float('inf') if net_annual_savings > 0 else 0
        payback_years = 0

    # NPV calculation
    npv = -total_implementation  # Initial investment
    for year in range(1, analysis_years + 1):
        npv += net_annual_savings / ((1 + discount_rate) ** year)

    # Savings breakdown
    savings_breakdown = blockchain.get_savings_breakdown(
        fraud_reduction_pct=scenario.fraud_reduction_pct
    )

    return ScenarioResults(
        scenario=scenario,
        traditional_cost=traditional_cost,
        blockchain_cost=blockchain_cost,
        net_savings=net_annual_savings,
        roi=roi,
        payback_years=payback_years,
        npv_5yr=npv,
        savings_breakdown=savings_breakdown
    )


def run_all_scenarios(params: PaymentFlowParams,
                       scenarios: Optional[Dict[str, AdoptionScenario]] = None,
                       discount_rate: float = 0.10) -> Dict[str, ScenarioResults]:

    if scenarios is None:
        scenarios = SCENARIOS

    results = {}
    for key, scenario in scenarios.items():
        results[key] = run_scenario_analysis(params, scenario, discount_rate)

    return results


def scenarios_to_dataframe(results: Dict[str, ScenarioResults]) -> pd.DataFrame:

    data = []
    for key, result in results.items():
        data.append({
            'scenario': result.scenario.name,
            'adoption_rate': f"{result.scenario.adoption_rate:.0%}",
            'effective_adoption': f"{result.scenario.effective_adoption:.0%}",
            'traditional_cost': result.traditional_cost,
            'blockchain_cost': result.blockchain_cost,
            'net_savings': result.net_savings,
            'roi': result.roi,
            'payback_years': result.payback_years,
            'npv_5yr': result.npv_5yr,
            'tx_cost': result.scenario.tx_cost_per_load,
            'fraud_reduction': f"{result.scenario.fraud_reduction_pct:.0%}",
            'regulatory_approval': result.scenario.regulatory_approval
        })

    return pd.DataFrame(data)


def calculate_breakeven_scenario(params: PaymentFlowParams,
                                  implementation_cost: float = 50_000_000,
                                  annual_maintenance: float = 10_000_000,
                                  tx_cost: float = 5.0) -> float:

    # Binary search for breakeven
    low, high = 0.001, 1.0
    target_payback = 3.0  # Target 3-year payback

    for _ in range(100):
        mid = (low + high) / 2
        scenario = AdoptionScenario(
            name='Test',
            adoption_rate=mid,
            shipper_escrow_pct=1.0,  # Remove constraints for this test
            carrier_tech_ready_pct=1.0,
            tx_cost_per_load=tx_cost,
            implementation_cost=implementation_cost,
            annual_maintenance_cost=annual_maintenance
        )

        result = run_scenario_analysis(params, scenario)

        if abs(result.payback_years - target_payback) < 0.1:
            return mid
        elif result.payback_years > target_payback or result.payback_years == float('inf'):
            low = mid
        else:
            high = mid

    return mid


def sensitivity_by_scenario_parameter(params: PaymentFlowParams,
                                       base_scenario: AdoptionScenario,
                                       parameter: str,
                                       values: List[float]) -> pd.DataFrame:

    results = []

    for value in values:
        # Create modified scenario
        scenario_dict = {
            'name': f'{base_scenario.name} ({parameter}={value})',
            'adoption_rate': base_scenario.adoption_rate,
            'shipper_escrow_pct': base_scenario.shipper_escrow_pct,
            'carrier_tech_ready_pct': base_scenario.carrier_tech_ready_pct,
            'tx_cost_per_load': base_scenario.tx_cost_per_load,
            'fraud_reduction_pct': base_scenario.fraud_reduction_pct,
            'regulatory_approval': base_scenario.regulatory_approval,
            'implementation_cost': base_scenario.implementation_cost,
            'annual_maintenance_cost': base_scenario.annual_maintenance_cost
        }
        scenario_dict[parameter] = value

        scenario = AdoptionScenario(**scenario_dict)
        result = run_scenario_analysis(params, scenario)

        results.append({
            'parameter_value': value,
            'net_savings': result.net_savings,
            'roi': result.roi,
            'payback_years': result.payback_years,
            'npv_5yr': result.npv_5yr
        })

    return pd.DataFrame(results)


def get_scenario_summary(results: Dict[str, ScenarioResults]) -> Dict[str, Any]:

    savings = [r.net_savings for r in results.values()]
    npvs = [r.npv_5yr for r in results.values()]
    paybacks = [r.payback_years for r in results.values() if r.payback_years != float('inf')]

    best_scenario = max(results.values(), key=lambda x: x.npv_5yr)
    worst_scenario = min(results.values(), key=lambda x: x.npv_5yr)

    return {
        'avg_annual_savings': np.mean(savings),
        'min_annual_savings': np.min(savings),
        'max_annual_savings': np.max(savings),
        'avg_npv_5yr': np.mean(npvs),
        'avg_payback_years': np.mean(paybacks) if paybacks else float('inf'),
        'best_scenario': best_scenario.scenario.name,
        'worst_scenario': worst_scenario.scenario.name,
        'all_positive_npv': all(npv > 0 for npv in npvs)
    }
