"""Summarize captures/bus_log.jsonl: per-byte constancy, ranges and trends for requests and replies.

Usage: python bus_analyze.py [note-substring]   (only frames whose note contains the substring)
Writes captures/bus_bytes.png (each varying byte vs time).
"""
import json, sys
import numpy as np

sel = sys.argv[1] if len(sys.argv) > 1 else ''
rows = [json.loads(l) for l in open('data/bus_log.jsonl')]
rows = [r for r in rows if r['sum_ok'] and sel in r.get('note', '')]
t0 = min(r['wall'] for r in rows)
out = {}
for kind, L in (('req', 16), ('rep', 26)):
    fr = [r for r in rows if r['kind'] == kind and len(r['bytes']) == L]
    if not fr:
        continue
    T = np.array([r['wall'] - t0 for r in fr]) / 60
    B = np.array([r['bytes'] for r in fr])
    out[kind] = (T, B)
    print(f'\n{kind}: {len(fr)} frames with good checksum over {T.max() - T.min():.1f} min')
    for i in range(L):
        col = B[:, i]
        u = np.unique(col)
        if len(u) == 1:
            print(f'  byte {i:2d}: constant 0x{u[0]:02X} ({u[0]})')
        else:
            first, last = col[:3].mean(), col[-3:].mean()
            corr = np.corrcoef(T, col)[0, 1] if np.std(col) > 0 else 0
            print(f'  byte {i:2d}: {len(u):2d} values, {col.min():3d}..{col.max():3d} '
                  f'(0x{col.min():02X}..0x{col.max():02X}), start ~{first:.0f} end ~{last:.0f}, trend r={corr:+.2f}'
                  + ('  bits: ' + ' '.join(f'{x:08b}' for x in u[:6]) if len(u) <= 6 else ''))
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    var = [(k, i) for k, (T, B) in out.items() for i in range(B.shape[1]) if len(np.unique(B[:, i])) > 1]
    fig, ax = plt.subplots(len(var), 1, figsize=(12, 1.6 * len(var)), sharex=True, squeeze=False)
    for a, (k, i) in zip(ax[:, 0], var):
        T, B = out[k]
        a.plot(T, B[:, i], '.-', ms=3)
        a.set_ylabel(f'{k}[{i}]')
        a.grid(True)
    ax[-1, 0].set_xlabel('minutes')
    fig.tight_layout()
    fig.savefig('figures/bus_bytes.png', dpi=90)
    print('\nplot captures/bus_bytes.png')
except Exception as e:
    print('plot failed', e)
