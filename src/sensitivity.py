"""Sensitivity analysis for blockchain freight payment models."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from .cost_model import PaymentFlowParams, BlockchainPaymentModel, TraditionalPaymentModel


@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    low_value: float
    high_value: float
    base_output: float
    low_output: float
    high_output: float
    sensitivity: float


def tornado_analysis(base_params: PaymentFlowParams,
                     param_ranges: Optional[Dict[str, Tuple[float, float]]] = None,
                     output_metric: str = 'net_savings',
                     adoption_rate: float = 0.30,
                     range_pct: float = 0.20) -> pd.DataFrame:
    # Default parameter ranges if not provided
    if param_ranges is None:
        param_ranges = {
            'dso_days': (
                base_params.dso_days * (1 - range_pct),
                base_params.dso_days * (1 + range_pct)
            ),
            'dpo_days': (
                base_params.dpo_days * (1 - range_pct),
                base_params.dpo_days * (1 + range_pct)
            ),
            'cost_of_capital': (
                base_params.cost_of_capital * (1 - range_pct),
                base_params.cost_of_capital * (1 + range_pct)
            ),
            'factoring_rate': (
                base_params.factoring_rate * (1 - range_pct),
                base_params.factoring_rate * (1 + range_pct)
            ),
            'fraud_loss_rate': (
                base_params.fraud_loss_rate * (1 - range_pct),
                base_params.fraud_loss_rate * (1 + range_pct)
            ),
            'annual_revenue': (
                base_params.annual_revenue * (1 - range_pct),
                base_params.annual_revenue * (1 + range_pct)
            ),
        }

    # Calculate base case output
    base_blockchain = BlockchainPaymentModel(base_params, adoption_rate)
    base_output = _get_output_metric(base_blockchain, output_metric)

    results = []

    for param_name, (low_val, high_val) in param_ranges.items():
        # Get base value
        base_val = getattr(base_params, param_name)

        # Test low value
        low_params = _modify_params(base_params, param_name, low_val)
        low_blockchain = BlockchainPaymentModel(low_params, adoption_rate)
        low_output = _get_output_metric(low_blockchain, output_metric)

        # Test high value
        high_params = _modify_params(base_params, param_name, high_val)
        high_blockchain = BlockchainPaymentModel(high_params, adoption_rate)
        high_output = _get_output_metric(high_blockchain, output_metric)

        # Calculate sensitivity
        if base_val != 0 and base_output != 0:
            pct_change_input = (high_val - low_val) / base_val
            pct_change_output = (high_output - low_output) / base_output
            sensitivity = pct_change_output / pct_change_input if pct_change_input != 0 else 0
        else:
            sensitivity = 0

        results.append({
            'parameter': param_name,
            'base_value': base_val,
            'low_value': low_val,
            'high_value': high_val,
            'base_output': base_output,
            'low_output': low_output,
            'high_output': high_output,
            'swing': abs(high_output - low_output),
            'sensitivity': sensitivity
        })

    df = pd.DataFrame(results)
    df = df.sort_values('swing', ascending=True)  # Ascending for tornado plot
    return df


def _modify_params(base_params: PaymentFlowParams,
                   param_name: str,
                   new_value: float) -> PaymentFlowParams:
    params_dict = {
        'annual_revenue': base_params.annual_revenue,
        'loads_per_year': base_params.loads_per_year,
        'dso_days': base_params.dso_days,
        'dpo_days': base_params.dpo_days,
        'cost_of_capital': base_params.cost_of_capital,
        'factoring_rate': base_params.factoring_rate,
        'fraud_loss_rate': base_params.fraud_loss_rate,
        'admin_cost_per_load': base_params.admin_cost_per_load,
        'days_in_year': base_params.days_in_year,
    }
    params_dict[param_name] = new_value
    return PaymentFlowParams(**params_dict)


def _get_output_metric(blockchain_model: BlockchainPaymentModel,
                       metric: str) -> float:
    if metric == 'net_savings':
        return blockchain_model.calculate_net_savings()
    elif metric == 'financing_savings':
        return blockchain_model.calculate_financing_savings()
    elif metric == 'factoring_savings':
        return blockchain_model.calculate_factoring_savings()
    elif metric == 'fraud_savings':
        return blockchain_model.calculate_reduced_fraud()
    elif metric == 'total_cost':
        return blockchain_model.total_cost()
    else:
        raise ValueError(f"Unknown metric: {metric}")


def spider_plot_data(params: PaymentFlowParams,
                     variables: Optional[List[str]] = None,
                     range_pct: float = 0.30,
                     n_points: int = 11,
                     adoption_rate: float = 0.30) -> pd.DataFrame:

    if variables is None:
        variables = ['dso_days', 'dpo_days', 'cost_of_capital',
                     'factoring_rate', 'fraud_loss_rate']

    # Generate percentage changes from -range_pct to +range_pct
    pct_changes = np.linspace(-range_pct, range_pct, n_points)

    # Calculate base output
    base_blockchain = BlockchainPaymentModel(params, adoption_rate)
    base_output = base_blockchain.calculate_net_savings()

    results = {'pct_change': pct_changes}

    for var in variables:
        base_val = getattr(params, var)
        outputs = []

        for pct in pct_changes:
            new_val = base_val * (1 + pct)
            modified_params = _modify_params(params, var, new_val)
            blockchain = BlockchainPaymentModel(modified_params, adoption_rate)
            output = blockchain.calculate_net_savings()
            # Normalize to percentage change from base
            normalized = (output - base_output) / base_output * 100 if base_output != 0 else 0
            outputs.append(normalized)

        results[var] = outputs

    return pd.DataFrame(results)


def monte_carlo_sensitivity(params: PaymentFlowParams,
                             distributions: Optional[Dict[str, Tuple[str, float, float]]] = None,
                             n_samples: int = 10_000,
                             adoption_rate: float = 0.30,
                             random_seed: Optional[int] = 42) -> Dict[str, Any]:

    if random_seed is not None:
        np.random.seed(random_seed)

    # Default distributions if not provided (using relative uncertainty)
    if distributions is None:
        distributions = {
            'dso_days': ('normal', params.dso_days, params.dso_days * 0.15),
            'dpo_days': ('normal', params.dpo_days, params.dpo_days * 0.10),
            'cost_of_capital': ('uniform', 0.05, 0.09),
            'factoring_rate': ('uniform', 0.02, 0.04),
            'fraud_loss_rate': ('triangular', 0.003, 0.005, 0.008),
            'adoption_rate': ('uniform', adoption_rate * 0.5, min(adoption_rate * 1.5, 1.0)),
        }

    # Generate samples for each parameter
    samples = {}
    for param_name, dist_spec in distributions.items():
        dist_type = dist_spec[0]
        if dist_type == 'normal':
            mean, std = dist_spec[1], dist_spec[2]
            samples[param_name] = np.random.normal(mean, std, n_samples)
        elif dist_type == 'uniform':
            low, high = dist_spec[1], dist_spec[2]
            samples[param_name] = np.random.uniform(low, high, n_samples)
        elif dist_type == 'triangular':
            left, mode, right = dist_spec[1], dist_spec[2], dist_spec[3]
            samples[param_name] = np.random.triangular(left, mode, right, n_samples)

    # Run simulations
    net_savings = np.zeros(n_samples)
    financing_savings = np.zeros(n_samples)
    factoring_savings = np.zeros(n_samples)
    fraud_savings = np.zeros(n_samples)

    for i in range(n_samples):
        # Build parameter set for this simulation
        sim_params = PaymentFlowParams(
            annual_revenue=params.annual_revenue,
            loads_per_year=params.loads_per_year,
            dso_days=samples.get('dso_days', np.full(n_samples, params.dso_days))[i],
            dpo_days=samples.get('dpo_days', np.full(n_samples, params.dpo_days))[i],
            cost_of_capital=samples.get('cost_of_capital', np.full(n_samples, params.cost_of_capital))[i],
            factoring_rate=samples.get('factoring_rate', np.full(n_samples, params.factoring_rate))[i],
            fraud_loss_rate=samples.get('fraud_loss_rate', np.full(n_samples, params.fraud_loss_rate))[i],
        )

        sim_adoption = samples.get('adoption_rate', np.full(n_samples, adoption_rate))[i]
        sim_adoption = np.clip(sim_adoption, 0.01, 1.0)

        blockchain = BlockchainPaymentModel(sim_params, sim_adoption)

        net_savings[i] = blockchain.calculate_net_savings()
        financing_savings[i] = blockchain.calculate_financing_savings()
        factoring_savings[i] = blockchain.calculate_factoring_savings()
        fraud_savings[i] = blockchain.calculate_reduced_fraud()

    # Calculate statistics
    return {
        'net_savings': {
            'samples': net_savings,
            'mean': np.mean(net_savings),
            'std': np.std(net_savings),
            'median': np.median(net_savings),
            'p5': np.percentile(net_savings, 5),
            'p95': np.percentile(net_savings, 95),
            'prob_positive': np.mean(net_savings > 0)
        },
        'financing_savings': {
            'samples': financing_savings,
            'mean': np.mean(financing_savings),
            'std': np.std(financing_savings),
        },
        'factoring_savings': {
            'samples': factoring_savings,
            'mean': np.mean(factoring_savings),
            'std': np.std(factoring_savings),
        },
        'fraud_savings': {
            'samples': fraud_savings,
            'mean': np.mean(fraud_savings),
            'std': np.std(fraud_savings),
        },
        'input_samples': samples,
        'n_samples': n_samples
    }


def calculate_value_drivers(params: PaymentFlowParams,
                             adoption_rate: float = 0.30) -> pd.DataFrame:

    blockchain = BlockchainPaymentModel(params, adoption_rate)

    drivers = {
        'Financing Savings': blockchain.calculate_financing_savings(),
        'Factoring Savings': blockchain.calculate_factoring_savings(),
        'Fraud Reduction': blockchain.calculate_reduced_fraud(),
        'Admin Savings': blockchain.calculate_admin_savings(),
        'Blockchain Costs': -blockchain.calculate_blockchain_tx_costs(),
    }

    total = sum(drivers.values())

    data = []
    for driver, value in drivers.items():
        data.append({
            'driver': driver,
            'value': value,
            'pct_of_total': value / total * 100 if total != 0 else 0
        })

    return pd.DataFrame(data)


def breakeven_probability(params: PaymentFlowParams,
                           distributions: Dict[str, Tuple[str, float, float]],
                           implementation_cost: float = 50_000_000,
                           years: int = 5,
                           n_samples: int = 10_000,
                           random_seed: Optional[int] = 42) -> Dict[str, float]:

    mc_results = monte_carlo_sensitivity(
        params, distributions, n_samples, random_seed=random_seed
    )

    annual_savings = mc_results['net_savings']['samples']
    total_savings_over_period = annual_savings * years

    # Probability of breakeven
    prob_breakeven = np.mean(total_savings_over_period > implementation_cost)

    # Probability of 2x return
    prob_2x = np.mean(total_savings_over_period > 2 * implementation_cost)

    # Expected NPV (simplified, no discounting)
    expected_npv = np.mean(total_savings_over_period) - implementation_cost

    return {
        'prob_breakeven': prob_breakeven,
        'prob_2x_return': prob_2x,
        'expected_npv': expected_npv,
        'median_savings': np.median(total_savings_over_period),
        'savings_p5': np.percentile(total_savings_over_period, 5),
        'savings_p95': np.percentile(total_savings_over_period, 95)
    }


def identify_key_uncertainties(tornado_results: pd.DataFrame,
                                threshold_pct: float = 0.10) -> List[str]:

    base_output = tornado_results['base_output'].iloc[0]
    threshold = abs(base_output) * threshold_pct

    significant = tornado_results[tornado_results['swing'] >= threshold]
    return significant['parameter'].tolist()
