"""Try to decode the AC indoor/outdoor current-loop bus as a UART from CH1 voltage captures.

Model: loop current ON makes the bus voltage fall, OFF lets it recover. So the current state is
estimated from the sign of the smoothed slope dV/dt (with hysteresis). UART idle (mark) = no current.

Usage: python uart_decode.py            -> scan baud/polarity/framing and report stop-bit validity
       python uart_decode.py 600 0 8N1  -> decode all hr_burst*.npy at that setting and print bytes
"""
import sys, glob
import numpy as np


def mavg(x, n):
    n = max(1, int(n))
    c = np.cumsum(np.insert(x, 0, 0))
    r = (c[n:] - c[:-n]) / n
    pad = len(x) - len(r)
    return np.concatenate([np.full(pad // 2, r[0]), r, np.full(pad - pad // 2, r[-1])])


def state_from_slope(t, v, smooth=0.4e-3, hyst=0.05):
    dt = t[1] - t[0]
    s = np.gradient(mavg(v, smooth / dt), dt) / 1e3          # V per ms
    st = np.empty(len(s), dtype=np.int8)
    cur = 1
    for i, x in enumerate(s):
        if x < -hyst:
            cur = 0            # falling -> current ON -> space (0)
        elif x > hyst:
            cur = 1            # rising  -> current OFF -> mark (1)
        st[i] = cur
    return st


def decode(t, st, baud, invert=False, nbits=8, parity=None, stop=1, vote=0.0):
    """Return list of (time, byte, ok).
    vote > 0: decide each bit by majority over the middle `vote` fraction of the bit cell
    (e.g. 0.5) instead of a single centre sample; much more robust to noise spikes."""
    dt = t[1] - t[0]
    b = st ^ 1 if invert else st
    T = 1.0 / baud
    nT = T / dt
    half = int(vote * nT / 2)
    frame = 1 + nbits + (1 if parity else 0) + stop
    out = []
    i = 1
    n = len(b)
    while i < n - int(frame * nT):
        if b[i - 1] == 1 and b[i] == 0:                     # falling edge = start bit
            def at(k):
                j = int(i + (k + 0.5) * nT)
                if j >= n:
                    return 1
                if half:
                    seg = b[max(0, j - half):min(n, j + half + 1)]
                    return 1 if seg.mean() >= 0.5 else 0
                return b[j]
            if at(0) != 0:
                i += 1
                continue
            bits = [at(1 + k) for k in range(nbits)]
            val = sum(int(bit) << k for k, bit in enumerate(bits))   # LSB first
            ok = True
            p_idx = 1 + nbits
            if parity:
                pb = at(p_idx)
                ones = sum(int(x) for x in bits) + int(pb)
                ok &= (ones % 2 == 0) if parity == 'E' else (ones % 2 == 1)
                p_idx += 1
            for k in range(stop):
                ok &= at(p_idx + k) == 1
            out.append((t[i], val, ok))
            i += int((frame - 0.5) * nT)
        else:
            i += 1
    return out


def load():
    files = sorted(glob.glob('captures/hr_burst*.npy'))
    return [(f, *np.load(f)) for f in files]


if __name__ == '__main__':
    data = load()
    states = [(f, t, state_from_slope(t, v)) for f, t, v in data]
    if len(sys.argv) == 1:
        res = []
        for baud in list(range(200, 2501, 25)):
            for inv in (False, True):
                for fr in ('8N1', '8E1', '8O1', '8N2'):
                    par = None if fr[1] == 'N' else fr[1]
                    stp = int(fr[2])
                    tot = okc = 0
                    for f, t, st in states:
                        fr_ = decode(t, st, baud, inv, 8, par, stp)
                        tot += len(fr_)
                        okc += sum(o for _, _, o in fr_)
                    if tot >= 20:
                        res.append((okc / tot, tot, baud, inv, fr))
        res.sort(reverse=True)
        print('best settings by stop/parity validity (fraction ok, frames, baud, inverted, framing):')
        for r in res[:15]:
            print(f'  {r[0]:.3f}  {r[1]:4d}  {r[2]:5d}  {"inv" if r[3] else "norm":4s}  {r[4]}')
    else:
        baud = int(sys.argv[1])
        inv = bool(int(sys.argv[2])) if len(sys.argv) > 2 else False
        fr = sys.argv[3] if len(sys.argv) > 3 else '8N1'
        par = None if fr[1] == 'N' else fr[1]
        for f, t, st in states:
            frames = decode(t, st, baud, inv, 8, par, int(fr[2]))
            ok = sum(o for _, _, o in frames)
            print(f'{f}: {len(frames)} frames, {ok} valid')
            print('  ' + ' '.join(f'{b:02X}' + ('' if o else '?') for _, b, o in frames))
