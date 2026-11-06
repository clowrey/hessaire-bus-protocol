"""Generate the README figures from the files in data/.  Run from the repo root:  python tools/make_figures.py"""
import json, os, sys, time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

sys.path.insert(0, os.path.dirname(__file__))
from uart_decode import decode

# ---- reference palette (light) ----
SURF, INK, INK2, MUTED, GRID, AXIS = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
REQ, REP = '#2a78d6', '#eb6834'                       # categorical slots 1, 2
CONF = {'confirmed': '#1c5cab', 'probable': '#3987e5', 'guess': '#86b6ef', 'unknown': '#e1e0d9'}
CONF_TEXT = {'confirmed': '#ffffff', 'probable': '#ffffff', 'guess': INK, 'unknown': INK2}

plt.rcParams.update({
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'font.family': ['Segoe UI', 'DejaVu Sans'], 'font.size': 10,
    'text.color': INK, 'axes.labelcolor': INK2, 'axes.edgecolor': AXIS,
    'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.titlecolor': INK, 'axes.titleweight': 'semibold',
    'axes.titlesize': 11, 'axes.titlelocation': 'left',
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
    'axes.spines.top': False, 'axes.spines.right': False,
    'lines.linewidth': 1.6, 'lines.solid_capstyle': 'round',
})
OUT = 'figures'
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=130, bbox_inches='tight')
    plt.close(fig)
    print('wrote', name)


# ---------- data ----------
rows = [json.loads(l) for l in open('data/bus_log.jsonl')]
good = [r for r in rows if r['sum_ok']]
# An 8-bit sum cannot catch some multi-bit errors (e.g. bit 7 flipped in four bytes adds 0x200 = 0 mod 256).
# Drop frames that break a byte which is constant in every other frame of that kind.
CONST = {'req': {0: 0x81, 6: 0x08, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0x23, 13: 0},
         'rep': {0: 0x28, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0x84, 7: 0, 14: 0, 22: 0, 24: 0x01}}
good = [r for r in good if all(r['bytes'][i] == c for i, c in CONST[r['kind']].items()
                               if len(r['bytes']) > i)]


def section(notes, kind, length):
    return [r for r in good if r.get('note') in notes and r['kind'] == kind and len(r['bytes']) == length]


def deg(b):
    return (b - 40) / 2.0


# ---------- 1. before / after repair ----------
b = np.load('data/envelope_before_repair.npz'); a = np.load('data/envelope_after_repair.npz')
fig, ax = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True, sharey=True)
ax[0].plot(b['t'], b['v'], color=INK2, lw=0.8)
ax[0].set_title('Before the repair: outdoor board dead, S wire idles at 24.8 V')
ax[0].annotate('weak 3–4 V sags every ~5 s\n(indoor unit polling, no answer)', xy=(-6.2, 21.5), xytext=(-8.9, 9),
               color=INK2, fontsize=9, arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
ax[1].plot(a['t'], a['v'], color=INK2, lw=0.8)
ax[1].set_title('After the repair: idle ~15 V, full-swing request and reply every ~5 s')
ax[1].annotate('indoor request\npulls S toward 0 V', xy=(-5.6, 0.5), xytext=(-8.6, 3), color=REQ, fontsize=9,
               arrowprops=dict(arrowstyle='-', color=REQ, lw=0.8))
ax[1].annotate('outdoor reply\npushes S to ~25 V', xy=(-4.8, 24.5), xytext=(-3.7, 19.5), color=REP, fontsize=9,
               arrowprops=dict(arrowstyle='-', color=REP, lw=0.8))
for x in ax:
    x.set_ylim(-3, 28); x.set_ylabel('S to earth (V)')
ax[0].set_ylim(-3, 28)
ax[1].set_xlabel('time (s), 10 s peak-detect envelope')
fig.tight_layout(); save(fig, 'before_after.png')

# ---------- 2. one exchange + decoded bits ----------
e = np.load('data/exchange_10s.npz')
v = e['mv'].astype(float) / 1000; dt = float(e['dt']); t = float(e['t0']) + np.arange(len(v)) * dt


def spans(mask, gap=0.05, minlen=0.05):
    idx = np.flatnonzero(mask); out = []
    for j in idx:
        if out and t[j] - out[-1][1] < gap: out[-1][1] = t[j]
        else: out.append([t[j], t[j]])
    return [(p, q) for p, q in out if q - p > minlen]


req_sp = spans(v < 7.0); rep_sp = spans(v > 21.0)
r0, r1 = req_sp[0]; p0, p1 = rep_sp[0]
fig = plt.figure(figsize=(11, 7.4))
gs = fig.add_gridspec(3, 1, height_ratios=[1.15, 1, 1.2], hspace=0.55)
ax0 = fig.add_subplot(gs[0])
ax0.plot(t, v, color=INK2, lw=0.6)
for (s0, s1) in req_sp: ax0.axvspan(s0, s1, color=REQ, alpha=0.12, lw=0)
for (s0, s1) in rep_sp: ax0.axvspan(s0, s1, color=REP, alpha=0.12, lw=0)
ax0.text((r0 + r1) / 2, 26.5, f'request\n{(r1 - r0) * 1e3:.0f} ms', color=REQ, ha='center', va='bottom', fontsize=9)
ax0.text((p0 + p1) / 2, 26.5, f'reply\n{(p1 - p0) * 1e3:.0f} ms', color=REP, ha='center', va='bottom', fontsize=9)
ax0.annotate('', xy=(req_sp[1][0], 1.5), xytext=(r0, 1.5), arrowprops=dict(arrowstyle='<->', color=MUTED, lw=0.8))
ax0.text((r0 + req_sp[1][0]) / 2, 2.2, f'{req_sp[1][0] - r0:.2f} s cycle', color=INK2, ha='center', fontsize=9)
ax0.set_ylim(-2, 32); ax0.set_ylabel('V'); ax0.set_xlabel('time (s)')
ax0.set_title('A 10 s capture: two request/reply exchanges')

ax1 = fig.add_subplot(gs[1])
m = (t > r0 - 0.08) & (t < p1 + 0.08)
ax1.plot(t[m], v[m], color=INK2, lw=0.6)
ax1.axvspan(r0, r1, color=REQ, alpha=0.12, lw=0); ax1.axvspan(p0, p1, color=REP, alpha=0.12, lw=0)
ax1.annotate('', xy=(p0, 9), xytext=(r1, 9), arrowprops=dict(arrowstyle='<->', color=MUTED, lw=0.8))
ax1.text((r1 + p0) / 2, 10, f'{(p0 - r1) * 1e3:.0f} ms', color=INK2, ha='center', fontsize=9)
ax1.text(r0 + 0.01, 27, '16 bytes from the indoor unit', color=REQ, fontsize=9, va='top')
ax1.text(p0 + 0.01, 3, '26 bytes from the outdoor unit', color=REP, fontsize=9)
ax1.set_ylim(-2, 29); ax1.set_ylabel('V'); ax1.set_xlabel('time (s)')
ax1.set_title('One exchange')

# bit-level zoom on the first 3 request bytes
mm = (t >= r0 - 0.06) & (t <= r1 + 0.06)
st = (v[mm] > 7.5).astype(np.int8)
frames = decode(t[mm], st, 300, False, 8, None, 1, vote=0.5)
ax2 = fig.add_subplot(gs[2])
T = 1 / 300
z0 = frames[0][0] - 0.004; z1 = frames[0][0] + 3 * 10 * T + 0.004
zm = (t >= z0) & (t <= z1)
ax2.plot((t[zm] - frames[0][0]) * 1e3, v[zm], color=REQ, lw=1.4)
for k, (ts, byte, ok) in enumerate(frames[:3]):
    base = (ts - frames[0][0]) * 1e3
    for bit in range(10):
        x0 = base + bit * T * 1e3
        ax2.axvline(x0, color=GRID, lw=0.8, zorder=0)
        if bit == 0: lab = 'S'
        elif bit == 9: lab = 'E'
        else: lab = str((byte >> (bit - 1)) & 1)
        ax2.text(x0 + T * 1e3 / 2, 17.6, lab, ha='center', va='bottom', fontsize=8,
                 color=INK2 if bit in (0, 9) else INK)
    ax2.text(base + 5 * T * 1e3, 21.2, f'byte {k} = 0x{byte:02X}', ha='center', fontsize=9.5, color=INK, weight='semibold')
ax2.set_xlim((z0 - frames[0][0]) * 1e3, (z1 - frames[0][0]) * 1e3)
ax2.set_ylim(-2, 24); ax2.set_ylabel('V'); ax2.set_xlabel('ms from the first start bit')
ax2.set_title('Bit level: 300 baud 8N1, LSB first.  S = start bit (line low), E = stop bit (line at idle), digits = data bits')
ax2.grid(False)
save(fig, 'exchange.png')

# ---------- 3. byte maps ----------
REQ_MAP = [
    ('0', 'header', 'unknown', '81'), ('1', 'setpoint', 'confirmed', '48'), ('2', 'room temp', 'probable', '62'),
    ('3', 'coil temp', 'probable', '45'), ('4', 'mode', 'confirmed', '82'), ('5', 'fan class', 'probable', '81'),
    ('6', '?', 'unknown', '08'), ('7', 'zero', 'unknown', '00'), ('8', 'zero', 'unknown', '00'),
    ('9', 'zero', 'unknown', '00'), ('10', 'zero', 'unknown', '00'), ('11', 'zero', 'unknown', '00'),
    ('12', '?', 'unknown', '23'), ('13', 'zero', 'unknown', '00'), ('14', 'fan step', 'probable', '02'),
    ('15', 'checksum', 'confirmed', 'sum'),
]
REP_MAP = [
    ('0', 'header', 'unknown', '28'), ('1', '? (with 8)', 'unknown', '34'), ('2', 'zero', 'unknown', '00'),
    ('3', 'zero', 'unknown', '00'), ('4', 'zero', 'unknown', '00'), ('5', 'zero', 'unknown', '00'),
    ('6', '?', 'unknown', '84'), ('7', 'zero', 'unknown', '00'), ('8', '? (with 1)', 'unknown', '34'),
    ('9', 'current?', 'guess', '24'), ('10', 'comp. target', 'probable', '4B'), ('11', 'comp. speed', 'probable', '52'),
    ('12', '?', 'unknown', '2B'), ('13', '?', 'unknown', '01'), ('14', 'zero', 'unknown', '00'),
    ('15', '? sensor', 'unknown', '45'), ('16', '? sensor', 'unknown', '4D'), ('17', 'discharge?', 'guess', '48'),
    ('18', 'room echo', 'confirmed', '62'), ('19', 'valve pos.', 'probable', '7B'), ('20', 'stage?', 'guess', '3F'),
    ('21', '?', 'unknown', '3C'), ('22', 'zero', 'unknown', '00'), ('23', 'start stage?', 'guess', '02'),
    ('24', '?', 'unknown', '01'), ('25', 'checksum', 'confirmed', 'sum'),
]


def byte_map(spec, per_row, title, color, name):
    nrow = int(np.ceil(len(spec) / per_row))
    W, H, gap = 1.0, 1.0, 0.08
    fig, ax = plt.subplots(figsize=(per_row * 0.92 + 0.4, nrow * 1.25 + 1.0))
    for i, (idx, label, conf, ex) in enumerate(spec):
        r, c = divmod(i, per_row)
        x, y = c * (W + gap), -r * (H + 0.38)
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle='round,pad=0,rounding_size=0.06',
                                    fc=CONF[conf], ec=SURF, lw=2))
        tc = CONF_TEXT[conf]
        ax.text(x + W / 2, y + H + 0.06, idx, ha='center', va='bottom', fontsize=8, color=MUTED)
        ax.text(x + W / 2, y + H * 0.60, ex, ha='center', va='center', fontsize=12, color=tc, weight='semibold',
                family='Consolas')
        ax.text(x + W / 2, y + H * 0.22, label, ha='center', va='center', fontsize=7.2, color=tc)
    ax.set_xlim(-0.1, per_row * (W + gap)); ax.set_ylim(-(nrow - 1) * (H + 0.38) - 0.15, H + 0.75)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title, color=color, loc='left')
    handles = [Rectangle((0, 0), 1, 1, fc=CONF[k], ec='none') for k in CONF]
    ax.legend(handles, ['confirmed by experiment', 'probable', 'guess', 'unknown / constant'],
              loc='upper center', bbox_to_anchor=(0.5, -0.02), ncol=4, frameon=False, fontsize=8.5,
              handlelength=1.2, handleheight=1.0, labelcolor=INK2)
    save(fig, name)


byte_map(REQ_MAP, 16, 'Indoor request: 16 bytes (example values in hex)', REQ, 'frame_request.png')
byte_map(REP_MAP, 13, 'Outdoor reply: 26 bytes (example values in hex)', REP, 'frame_reply.png')

# ---------- 4. setpoint experiment ----------
q = section({'experiment'}, 'req', 16); p = section({'experiment'}, 'rep', 26)
t0 = q[0]['wall']
tq = np.array([r['wall'] - t0 for r in q]) / 60; tp = np.array([r['wall'] - t0 for r in p]) / 60
sp = np.array([deg(r['bytes'][1]) for r in q]); tgt = np.array([r['bytes'][10] for r in p])
fig, ax = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True)
ax[0].step(tq, sp, where='post', color=REQ, lw=2)
ax[0].plot(tq, sp, 'o', color=REQ, ms=3.5, mec=SURF, mew=0.8)
labels = [(0.0, '61°F\nturbo'), (1.15, '75°F\nturbo off'), (1.6, '65°F'), (4.1, '70°F'), (4.45, '75°F'),
          (4.75, '80°F'), (5.8, '70°F')]
for x, lab in labels:
    i = np.searchsorted(tq, x + 0.02); i = min(i, len(sp) - 1)
    ax[0].text(x + 0.05, sp[i] + 0.6, lab, fontsize=8.5, color=INK2, va='bottom')
ax[0].set_ylim(14, 31); ax[0].set_ylabel('°C  =  (byte − 40) / 2')
ax[0].set_title('Request byte 1 follows every setpoint change on the remote')
ax[1].step(tp, tgt, where='post', color=REP, lw=2)
ax[1].set_ylim(50, 80); ax[1].set_ylabel('raw value')
ax[1].set_title('Reply byte 10 (compressor target?) drops as the setpoint nears the 29 °C room')
ax[1].set_xlabel('minutes into the experiment')
fig.tight_layout(); save(fig, 'setpoint.png')

# ---------- 5. mode experiment ----------
q = section({'modes', 'experiment2'}, 'req', 16); p = section({'modes', 'experiment2'}, 'rep', 26)
q = [r for r in q if r['wall'] > good[-1]['wall'] - 99999]
tA = min(r['wall'] for r in section({'modes'}, 'req', 16)) - 60
q = [r for r in q if r['wall'] >= tA]; p = [r for r in p if r['wall'] >= tA]
tq = np.array([r['wall'] - tA for r in q]) / 60; tp = np.array([r['wall'] - tA for r in p]) / 60
mode_code = {0x82: 2, 0x83: 1, 0x80: 0}
mv = np.array([mode_code.get(r['bytes'][4], np.nan) for r in q])
fig, ax = plt.subplots(4, 1, figsize=(10, 7.4), sharex=True, gridspec_kw={'height_ratios': [1, 1, 1, 0.8]})
ax[0].step(tq, mv, where='post', color=REQ, lw=2)
ax[0].set_yticks([0, 1, 2]); ax[0].set_yticklabels(['Fan only  0x80', 'Dry  0x83', 'Cool  0x82'])
ax[0].set_ylim(-0.5, 2.5); ax[0].set_title('Request byte 4 = mode')
ax[1].step(tp, [r['bytes'][10] for r in p], where='post', color=REP, lw=2)
ax[1].set_ylim(-5, 85); ax[1].set_title('Reply byte 10: compressor target (0 in Fan only, 60 in Dry)')
ax[2].step(tp, [r['bytes'][11] for r in p], where='post', color=REP, lw=2)
ax[2].set_ylim(-5, 95); ax[2].set_title('Reply byte 11: compressor speed (stops ~10 s after Fan only, waits to restart)')
ax[3].step(tp, [r['bytes'][23] for r in p], where='post', color=REP, lw=2)
ax[3].set_ylim(-0.5, 2.5); ax[3].set_yticks([0, 1, 2]); ax[3].set_title('Reply byte 23: stays 0 here, even after the restart (it read 1, then 2, during the first start-up)')
ax[3].set_xlabel('minutes')
for x in ax[1:3]: x.set_ylabel('raw')
fig.tight_layout(); save(fig, 'modes.png')

# ---------- 6. start-up trends ----------
q = section({'running after repair, unchanged settings', 'running, settings unchanged (61F max fan super)'}, 'req', 16)
p = section({'running after repair, unchanged settings', 'running, settings unchanged (61F max fan super)'}, 'rep', 26)
# first decoded exchange (from the 10 s record) as t = 0
first_req = [f[1] for f in frames]
mm = (t >= p0 - 0.06) & (t <= p1 + 0.06)
first_rep = [f[1] for f in decode(t[mm], (v[mm] < 20).astype(np.int8), 300, False, 8, None, 1, vote=0.5)]
tw0 = float(e['wall_end']) + t[0] + (r0 - t[0])
W = [tw0] + [r['wall'] for r in q]; Q = [first_req] + [r['bytes'] for r in q]
WP = [tw0 + 0.6] + [r['wall'] for r in p]; P = [first_rep] + [r['bytes'] for r in p]
tq = (np.array(W) - tw0) / 60; tp = (np.array(WP) - tw0) / 60


def gapped(x, y, gap=1.5):
    x = np.asarray(x, float); y = np.asarray(y, float)
    cut = np.flatnonzero(np.diff(x) > gap) + 1
    return np.insert(x, cut, np.nan), np.insert(y, cut, np.nan)


fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
ax[0].plot(*gapped(tq, [deg(b[2]) for b in Q]), color=REQ, lw=2, marker='o', ms=3, mec=SURF, mew=0.6)
ax[0].plot(*gapped(tq, [deg(b[3]) for b in Q]), color=REP, lw=2, marker='o', ms=3, mec=SURF, mew=0.6)
ax[0].text(tq[-1] + 0.1, deg(Q[-1][2]), 'room (byte 2)', color=INK2, va='center', fontsize=9)
ax[0].text(tq[-1] + 0.1, deg(Q[-1][3]), 'indoor coil (byte 3)', color=INK2, va='center', fontsize=9)
ax[0].legend(['request byte 2: room', 'request byte 3: indoor coil'], loc='center', bbox_to_anchor=(0.42, 0.62), frameon=False, fontsize=8.5)
ax[0].set_ylabel('°C'); ax[0].set_title('Indoor temperatures after start-up, (byte − 40) / 2')
ax[1].plot(*gapped(tp, [b[11] for b in P]), color=REP, lw=2, marker='o', ms=3, mec=SURF, mew=0.6)
ax[1].set_ylabel('raw'); ax[1].set_title('Reply byte 11 (compressor speed?): 56 at start, 112 three minutes later, then about 85')
ax[2].plot(*gapped(tp, [b[17] for b in P]), color=REP, lw=2, marker='o', ms=3, mec=SURF, mew=0.6)
ax[2].set_ylabel('raw'); ax[2].set_title('Reply byte 17: climbs steadily (discharge temperature in °C?)')
ax[2].set_xlabel('minutes after the first decoded exchange (gaps = logger not running)')
ax[0].set_xlim(-0.2, tq[-1] + 2.0)
fig.tight_layout(); save(fig, 'startup.png')
print('first request :', ' '.join(f'{x:02X}' for x in first_req))
print('first reply   :', ' '.join(f'{x:02X}' for x in first_rep))

# ---------- byte ranges for the README tables ----------
for kind, L in (('req', 16), ('rep', 26)):
    B = np.array([r['bytes'] for r in good if r['kind'] == kind and len(r['bytes']) == L])
    print(kind, len(B), 'frames; per-byte min..max:',
          ', '.join(f'{i}:{B[:, i].min():02X}..{B[:, i].max():02X}' for i in range(L)))
