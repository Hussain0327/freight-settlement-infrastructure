"""Blockchain freight payment infrastructure analysis package."""

from .utils import (
    load_stock_data,
    extract_10k_metrics,
    calculate_dso,
    calculate_dpo,
    calculate_cash_conversion_cycle,
    format_currency,
    CHRW_10K_DATA,
)

from .cost_model import (
    PaymentFlowParams,
    TraditionalPaymentModel,
    BlockchainPaymentModel,
    compare_models,
    calculate_breakeven_adoption,
    sensitivity_to_adoption,
)

from .working_capital import (
    SimulationParams,
    SimulationResults,
    WorkingCapitalSimulator,
    calculate_risk_reduction,
)

from .scenarios import (
    AdoptionScenario,
    ScenarioResults,
    SCENARIOS,
    run_scenario_analysis,
    run_all_scenarios,
    scenarios_to_dataframe,
)

from .sensitivity import (
    tornado_analysis,
    spider_plot_data,
    monte_carlo_sensitivity,
    calculate_value_drivers,
)

__version__ = "0.1.0"
__author__ = "Research Team"

__all__ = [
    # Utils
    'load_stock_data',
    'extract_10k_metrics',
    'calculate_dso',
    'calculate_dpo',
    'calculate_cash_conversion_cycle',
    'format_currency',
    'CHRW_10K_DATA',
    # Cost Model
    'PaymentFlowParams',
    'TraditionalPaymentModel',
    'BlockchainPaymentModel',
    'compare_models',
    'calculate_breakeven_adoption',
    'sensitivity_to_adoption',
    # Working Capital
    'SimulationParams',
    'SimulationResults',
    'WorkingCapitalSimulator',
    'calculate_risk_reduction',
    # Scenarios
    'AdoptionScenario',
    'ScenarioResults',
    'SCENARIOS',
    'run_scenario_analysis',
    'run_all_scenarios',
    'scenarios_to_dataframe',
    # Sensitivity
    'tornado_analysis',
    'spider_plot_data',
    'monte_carlo_sensitivity',
    'calculate_value_drivers',
]
