"""Run the reference water-in-argon case and render the README figure.

Produces ``docs/assets/reference_case.png``: the d^2 evaporation history with
the accumulating vapour content, and the droplet heating transient. The final
stored state is the one that triggers the run's stop condition and is excluded
from the plots. Run from the repository root:

    python examples/plot_reference_case.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from dropletevapmodel import DropletEvapModel, EvapModel, load_config

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = load_config(str(ROOT / 'configs' / 'config.yml'))
    config['gas_properties'] = pd.read_csv(
        ROOT / 'configs' / 'gas.csv', index_col='property')['Ar'].to_dict()
    config['fluid_properties'] = pd.read_csv(
        ROOT / 'configs' / 'liq.csv', index_col='property')['H2O'].to_dict()

    result = EvapModel(DropletEvapModel(**config)).run()
    steps = sorted(result)[:-1]          # drop the stop-triggering terminal state

    time = np.array([result[t]['time'] for t in steps])
    d_square = np.array([result[t]['d_d'] for t in steps]) ** 2 * 1e12   # um^2
    t_drop = np.array([result[t]['t_d'] for t in steps])
    ppm = np.array([result[t]['ppm'] for t in steps])

    fig, ax = plt.subplots(1, 2, figsize=(11, 4))

    (line,) = ax[0].plot(time, d_square, lw=2.2, color='#0b6e4f')
    ax[0].set_xlabel('Time (s)')
    ax[0].set_ylabel(r'Squared diameter $d^2$ ($\mu m^2$)', color='#0b6e4f')
    ax[0].tick_params(axis='y', labelcolor='#0b6e4f')
    ax[0].set_title(r'$d^2$-law evaporation: water droplet in argon')
    ax0b = ax[0].twinx()
    ax0b.plot(time, ppm, lw=1.4, ls='--', color='#b3541e')
    ax0b.set_ylabel('Vapour content (ppm)', color='#b3541e')
    ax0b.tick_params(axis='y', labelcolor='#b3541e')

    ax[1].plot(time, t_drop, lw=2.2, color='#1f4e79')
    ax[1].set_xlabel('Time (s)')
    ax[1].set_ylabel('Droplet temperature (K)')
    ax[1].set_title('Droplet heating transient')

    for axis in ax:
        axis.spines['top'].set_visible(False)
    fig.tight_layout()

    out = ROOT / 'docs' / 'assets' / 'reference_case.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=160)
    print(f'Saved {out} ({len(steps)} accepted states, '
          f'final time {time[-1]:.5f} s)')


if __name__ == '__main__':
    main()
