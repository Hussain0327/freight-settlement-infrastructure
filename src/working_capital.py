"""Monte Carlo simulation for working capital risk analysis."""

from dataclasses import dataclass
from typing import Optional, Dict, List
import numpy as np


@dataclass
class SimulationParams:
    n_simulations: int = 10_000
    simulation_days: int = 365
    loads_per_day: int = 43_014
    shipper_payment_mean: float = 49.0
    shipper_payment_std: float = 15.0
    carrier_payment_mean: float = 27.0
    carrier_payment_std: float = 5.0
    revenue_per_load_mean: float = 1_127.0
    revenue_per_load_std: float = 500.0
    blockchain_settlement_days: float = 0.5
    random_seed: Optional[int] = 42

    def __post_init__(self):
        if self.random_seed is not None:
            np.random.seed(self.random_seed)


@dataclass
class SimulationResults:
    daily_positions: np.ndarray
    mean_position: np.ndarray
    std_position: np.ndarray
    var_95: float
    var_99: float
    cvar_95: float
    max_drawdown: float
    peak_capital_required: float

    def summary(self) -> Dict[str, float]:
        return {
            'mean_daily_position': float(np.mean(self.mean_position)),
            'std_daily_position': float(np.mean(self.std_position)),
            'var_95': self.var_95,
            'var_99': self.var_99,
            'cvar_95': self.cvar_95,
            'max_drawdown': self.max_drawdown,
            'peak_capital_required': self.peak_capital_required
        }


class WorkingCapitalSimulator:
    def __init__(self, params: SimulationParams):
        self.params = params

    def _generate_load_revenues(self, n_days: int) -> np.ndarray:
        revenues = np.random.normal(
            self.params.revenue_per_load_mean,
            self.params.revenue_per_load_std,
            (n_days, self.params.loads_per_day)
        )
        return np.maximum(revenues, 100)

    def _generate_payment_timing(self, n_loads: int, mean: float,
                                  std: float, min_days: float = 1.0) -> np.ndarray:
        timing = np.random.normal(mean, std, n_loads)
        return np.maximum(timing, min_days).astype(int)

    def simulate_traditional(self) -> np.ndarray:
        n_sims = self.params.n_simulations
        n_days = self.params.simulation_days
        all_positions = np.zeros((n_sims, n_days))

        for sim in range(n_sims):
            cumulative_outflows = np.zeros(n_days)
            cumulative_inflows = np.zeros(n_days)

            for day in range(n_days):
                n_loads = self.params.loads_per_day
                revenues = np.random.normal(
                    self.params.revenue_per_load_mean,
                    self.params.revenue_per_load_std,
                    n_loads
                )
                revenues = np.maximum(revenues, 100)

                carrier_days = self._generate_payment_timing(
                    n_loads, self.params.carrier_payment_mean,
                    self.params.carrier_payment_std, min_days=1.0
                )
                shipper_days = self._generate_payment_timing(
                    n_loads, self.params.shipper_payment_mean,
                    self.params.shipper_payment_std, min_days=1.0
                )

                for i, (rev, carrier_day) in enumerate(zip(revenues, carrier_days)):
                    payment_day = min(day + carrier_day, n_days - 1)
                    cumulative_outflows[payment_day:] += rev * 0.85

                for i, (rev, shipper_day) in enumerate(zip(revenues, shipper_days)):
                    collection_day = min(day + shipper_day, n_days - 1)
                    cumulative_inflows[collection_day:] += rev

            all_positions[sim] = cumulative_outflows - cumulative_inflows

        return all_positions

    def simulate_traditional_fast(self) -> np.ndarray:
        n_sims = self.params.n_simulations
        n_days = self.params.simulation_days

        daily_revenue = self.params.loads_per_day * self.params.revenue_per_load_mean
        daily_revenue_std = np.sqrt(self.params.loads_per_day) * self.params.revenue_per_load_std

        daily_revenues = np.random.normal(daily_revenue, daily_revenue_std, (n_sims, n_days))
        daily_revenues = np.maximum(daily_revenues, daily_revenue * 0.5)

        dso_variations = np.random.normal(
            self.params.shipper_payment_mean, self.params.shipper_payment_std, (n_sims, n_days)
        )
        dpo_variations = np.random.normal(
            self.params.carrier_payment_mean, self.params.carrier_payment_std, (n_sims, n_days)
        )

        gap_days = dso_variations - dpo_variations
        all_positions = np.zeros((n_sims, n_days))

        for sim in range(n_sims):
            position = 0
            for day in range(n_days):
                new_requirement = daily_revenues[sim, day] * gap_days[sim, day] / n_days
                position = position * 0.98 + new_requirement
                all_positions[sim, day] = position

        return all_positions

    def simulate_blockchain(self, adoption_rate: float = 0.30) -> np.ndarray:
        n_sims = self.params.n_simulations
        n_days = self.params.simulation_days
        bc_settlement = self.params.blockchain_settlement_days

        daily_revenue = self.params.loads_per_day * self.params.revenue_per_load_mean
        daily_revenue_std = np.sqrt(self.params.loads_per_day) * self.params.revenue_per_load_std

        daily_revenues = np.random.normal(daily_revenue, daily_revenue_std, (n_sims, n_days))
        daily_revenues = np.maximum(daily_revenues, daily_revenue * 0.5)

        dso_mean = (1 - adoption_rate) * self.params.shipper_payment_mean + adoption_rate * bc_settlement
        dso_std = (1 - adoption_rate) * self.params.shipper_payment_std
        dpo_mean = (1 - adoption_rate) * self.params.carrier_payment_mean + adoption_rate * bc_settlement
        dpo_std = (1 - adoption_rate) * self.params.carrier_payment_std

        dso_variations = np.random.normal(dso_mean, dso_std, (n_sims, n_days))
        dpo_variations = np.random.normal(dpo_mean, dpo_std, (n_sims, n_days))
        gap_days = dso_variations - dpo_variations

        all_positions = np.zeros((n_sims, n_days))
        for sim in range(n_sims):
            position = 0
            for day in range(n_days):
                new_requirement = daily_revenues[sim, day] * gap_days[sim, day] / n_days
                position = position * 0.98 + new_requirement
                all_positions[sim, day] = position

        return all_positions

    def calculate_var(self, positions: np.ndarray, confidence: float = 0.95) -> float:
        peak_positions = np.max(positions, axis=1)
        return np.percentile(peak_positions, confidence * 100)

    def calculate_expected_shortfall(self, positions: np.ndarray, confidence: float = 0.95) -> float:
        peak_positions = np.max(positions, axis=1)
        var_threshold = np.percentile(peak_positions, confidence * 100)
        tail_positions = peak_positions[peak_positions >= var_threshold]
        return np.mean(tail_positions) if len(tail_positions) > 0 else var_threshold

    def calculate_max_drawdown(self, positions: np.ndarray) -> float:
        max_drawdowns = []
        for sim_positions in positions:
            running_max = np.maximum.accumulate(sim_positions)
            drawdowns = running_max - sim_positions
            max_drawdowns.append(np.max(drawdowns))
        return np.percentile(max_drawdowns, 95)

    def run_monte_carlo(self, use_fast: bool = True) -> SimulationResults:
        if use_fast:
            positions = self.simulate_traditional_fast()
        else:
            positions = self.simulate_traditional()

        mean_position = np.mean(positions, axis=0)
        std_position = np.std(positions, axis=0)
        var_95 = self.calculate_var(positions, 0.95)
        var_99 = self.calculate_var(positions, 0.99)
        cvar_95 = self.calculate_expected_shortfall(positions, 0.95)
        max_dd = self.calculate_max_drawdown(positions)
        peak_capital = np.percentile(np.max(positions, axis=1), 95)

        return SimulationResults(
            daily_positions=positions,
            mean_position=mean_position,
            std_position=std_position,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            max_drawdown=max_dd,
            peak_capital_required=peak_capital
        )

    def run_comparative_simulation(self, adoption_rates: Optional[List[float]] = None) -> Dict[str, SimulationResults]:
        if adoption_rates is None:
            adoption_rates = [0.0, 0.10, 0.30, 0.50, 0.75, 1.0]

        results = {}
        for rate in adoption_rates:
            if rate == 0.0:
                positions = self.simulate_traditional_fast()
            else:
                positions = self.simulate_blockchain(rate)

            mean_position = np.mean(positions, axis=0)
            std_position = np.std(positions, axis=0)
            var_95 = self.calculate_var(positions, 0.95)
            var_99 = self.calculate_var(positions, 0.99)
            cvar_95 = self.calculate_expected_shortfall(positions, 0.95)
            max_dd = self.calculate_max_drawdown(positions)
            peak_capital = np.percentile(np.max(positions, axis=1), 95)

            results[f'{rate:.0%}'] = SimulationResults(
                daily_positions=positions,
                mean_position=mean_position,
                std_position=std_position,
                var_95=var_95,
                var_99=var_99,
                cvar_95=cvar_95,
                max_drawdown=max_dd,
                peak_capital_required=peak_capital
            )

        return results


def calculate_risk_reduction(traditional_results: SimulationResults,
                              blockchain_results: SimulationResults) -> Dict[str, float]:
    return {
        'var_95_reduction': traditional_results.var_95 - blockchain_results.var_95,
        'var_95_reduction_pct': (
            (traditional_results.var_95 - blockchain_results.var_95) /
            traditional_results.var_95 * 100
            if traditional_results.var_95 > 0 else 0
        ),
        'cvar_95_reduction': traditional_results.cvar_95 - blockchain_results.cvar_95,
        'peak_capital_reduction': (
            traditional_results.peak_capital_required - blockchain_results.peak_capital_required
        ),
        'volatility_reduction': (
            np.mean(traditional_results.std_position) - np.mean(blockchain_results.std_position)
        )
    }
