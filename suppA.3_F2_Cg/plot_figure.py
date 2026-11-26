"""Recreate the n=13--16 seed-progress figure from the audited CSV."""
import argparse
import csv
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='New output directory')
    args = ap.parse_args()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    source = Path(__file__).resolve().parent/'figures/seed_progress_small_orders_20261125.csv'
    with source.open() as f:
        records = list(csv.DictReader(f))
    args.out.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({'font.family':'serif','font.size':9,'pdf.fonttype':42,'ps.fonttype':42})
    fig, axes = plt.subplots(2,2,figsize=(6.7,4.7),layout='constrained')
    styles = {'RNBP':('#0072B2','-'),'A1':('#D55E00','--'),'A2':('#009E73','-.')}
    for n, ax in zip((13,14,15,16),axes.flat):
        for algorithm,(color,style) in styles.items():
            rows = sorted((r for r in records if int(r['n'])==n and r['algorithm']==algorithm),
                          key=lambda r:int(r['seeds_per_matrix']))
            ax.step([int(r['seeds_per_matrix']) for r in rows],
                    [int(r['best_xor_gates']) for r in rows],where='post',
                    label=algorithm,color=color,linestyle=style)
        ax.set(title=f'n={n}',xlabel='Seeds per matrix and algorithm',ylabel='Best XOR gate count',xlim=(0,101))
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(axis='y',alpha=.2)
        ax.legend(frameon=False)
    fig.savefig(args.out/'seed_progress.pdf')
    fig.savefig(args.out/'seed_progress.png',dpi=220)
    plt.close(fig)


if __name__=='__main__':
    main()
