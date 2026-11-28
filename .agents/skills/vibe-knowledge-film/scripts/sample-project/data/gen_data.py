"""Deterministic data for 《稳定的形状》. Every number shown on screen comes from here.
Seed is fixed; run twice -> identical data.json (checked by tools/verify.py)."""
import json, math, numpy as np
from fractions import Fraction
SEED = 20261013
rng = np.random.Generator(np.random.PCG64(SEED))
N, P = 10000, 60                      # 60 simulated people x 10,000 fair-coin tosses
flips = rng.integers(0, 2, size=(P, N), dtype=np.int8)   # 1 = 正面
cum = flips.cumsum(1); n = np.arange(1, N+1)
prop = cum / n
# log-spaced sample points for drawing
pts = np.unique(np.round(np.logspace(0, 4, 420)).astype(int))
# highlighted path: first person (in index order) whose |H-T| grows clearly (illustrates gambler's fallacy honestly)
diff = 2*cum - n
cand = [i for i in range(P) if flips[i,0]==1 and abs(diff[i,99])>=4 and diff[i,99]*diff[i,-1]>0]
hl = max(cand, key=lambda i: abs(diff[i,-1]))
ranges = {}
for k in (10, 100, 1000, 10000):
    v = prop[:, k-1]; ranges[k] = [float(v.min()), float(v.max())]
# exact binomial: share of sequences with proportion in [0.4, 0.6]
def share(nn):
    lo, hi = math.ceil(0.4*nn), math.floor(0.6*nn)
    return Fraction(sum(math.comb(nn, k) for k in range(lo, hi+1)), 2**nn)
shares = {nn: share(nn) for nn in (4, 10, 100, 1000)}
def pmf(nn): return [math.comb(nn,k)/2**nn for k in range(nn+1)]
# dice: 3,000 rolls of a fair die, running mean
rng_d = np.random.Generator(np.random.PCG64(SEED+1))
dice = rng_d.integers(1, 7, size=3000)
dmean = dice.cumsum()/np.arange(1,3001)
dpts = np.unique(np.round(np.logspace(0, math.log10(3000), 300)).astype(int))
# counter-example: standard Cauchy running mean (has no mean, never settles)
rng_c = np.random.Generator(np.random.PCG64(SEED+2))
cau = rng_c.standard_cauchy(10000); cmean = cau.cumsum()/n
seq10 = flips[hl,:10].tolist(); p10 = [float(x) for x in prop[hl,:10]]
H = int(cum[hl,-1])
data = {
 'seed': SEED, 'people': P, 'tosses': N, 'highlight': hl,
 'highlight_rule': 'among paths whose first toss is 正 and whose gap at n=100 (|H-T|>=4) has the same sign as at n=10000, the one with the largest |H-T| at n=10000 (illustrates: gap grows while proportion settles)',
 'pts': pts.tolist(),
 'paths': [[round(float(prop[i,k-1]),5) for k in pts] for i in range(P)],
 'hl_diff': [int(diff[hl,k-1]) for k in pts],
 'seq10': seq10, 'p10': p10, 'ranges': {str(k):v for k,v in ranges.items()},
 'hl_final': {'heads': H, 'tails': N-H, 'diff': int(diff[hl,-1]), 'diff100': int(diff[hl,99]), 'prop': H/N},
 'shares': {str(k): float(v) for k,v in shares.items()},
 'shares_exact': {str(k): f'{v.numerator}/{v.denominator}' if k<=10 else None for k,v in shares.items()},
 'pmf': {str(k): pmf(k) for k in (4,10,100,1000)},
 'dice_first': dice[:6].tolist(), 'dice_pts': dpts.tolist(),
 'dice_mean': [round(float(dmean[k-1]),4) for k in dpts], 'dice_final': float(dmean[-1]),
 'cauchy_pts': pts.tolist(), 'cauchy_mean': [round(float(cmean[k-1]),4) for k in pts],
 'kerrich': {'tosses': 10000, 'heads': 5067, 'source': 'J. E. Kerrich, An Experimental Introduction to the Theory of Probability (1946); Wikipedia "John Edmund Kerrich"'},
}
pct = lambda x, d=0: f'{x*100:.{d}f}%'
r10 = ranges[10]; r1e4 = ranges[10000]
mn10 = min(p10)
data['facts'] = {
 'heads10': sum(seq10), 'min10': pct(mn10), 'max10': pct(max(p10)),
 'range10': f'{pct(r10[0])}–{pct(r10[1])}', 'range100': f'{pct(ranges[100][0])}–{pct(ranges[100][1])}',
 'range1000': f'{pct(ranges[1000][0],1)}–{pct(ranges[1000][1],1)}', 'range10000': f'{pct(r1e4[0],1)}–{pct(r1e4[1],1)}',
 'share4_count': math.comb(4,2), 'share4_total': 16, 'share10_count': sum(math.comb(10,k) for k in (4,5,6)), 'share10': pct(float(shares[10]),1),
 'share100': pct(float(shares[100]),1), 'share1000_gt': '99.999999%' if float(shares[1000])>0.99999999 else pct(float(shares[1000]),4),
 'hl_diff100': int(diff[hl,99]), 'hl_prop100': pct(cum[hl,99]/100), 'hl_dev100': f'{abs(cum[hl,99]/100-0.5)*100:.0f}', 'hl_dev': f'{abs(H/N-0.5)*100:.2f}', 'hl_diff': int(diff[hl,-1]), 'hl_prop': pct(H/N,2),
 'dice_final': f'{dmean[-1]:.3f}',
 'abs_diff100': abs(int(diff[hl,99])), 'abs_diff': abs(int(diff[hl,-1])),
 'lead_side': '反面' if diff[hl,-1] < 0 else '正面', 'catchup_side': '正面' if diff[hl,-1] < 0 else '反面',
}
json.dump(data, open('data/data.json','w'), ensure_ascii=False)
print(json.dumps({k:data[k] for k in ('highlight','seq10','p10','ranges','hl_final','shares','dice_first','dice_final','facts')}, ensure_ascii=False, indent=1))
print('cauchy sample', [data['cauchy_mean'][i] for i in range(0,len(pts),40)])
