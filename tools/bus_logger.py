"""Log decoded indoor/outdoor S-wire frames from the DHO804, CH1, continuously.

Each cycle: 10 s roll capture at 1 s/div (5 Mpts, 2 us), 16-bit read, decimate to 10 us,
find request bursts (line pulled below ~7.5 V) and reply bursts (pushed above ~20 V),
decode as 300 baud 8N1, check the sum checksum, append to captures/bus_log.jsonl.

Usage: python bus_logger.py [minutes] [note]
"""
import json, sys, time
import numpy as np
from dho_scpi import Scope
from uart_decode import decode

MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 5
NOTE = sys.argv[2] if len(sys.argv) > 2 else ''
OUT = 'data/bus_log.jsonl'


def spans(td, m, gap=0.05, minlen=0.05):
    idx = np.flatnonzero(m)
    out = []
    for j in idx:
        if out and td[j] - out[-1][1] < gap:
            out[-1][1] = td[j]
        else:
            out.append([td[j], td[j]])
    return [(a, b) for a, b in out if b - a > minlen]


def frames_from(td, vd):
    res = []
    for kind, mask, thr_state in (('req', vd < 7.0, lambda x: (x > 7.5)),
                                  ('rep', vd > 21.0, lambda x: (x < 20.0))):
        for a, b in spans(td, mask):
            m = (td >= a - 0.04) & (td <= b + 0.06)
            st = thr_state(vd[m]).astype(np.int8)
            fr = decode(td[m], st, 300, False, 8, None, 1, vote=0.5)
            by = [int(x) for _, x, _ in fr]
            okstop = all(o for *_, o in fr)
            ck = len(by) > 1 and (sum(by[:-1]) & 0xFF) == by[-1]
            res.append({'kind': kind, 't': float(a), 'bytes': by, 'stop_ok': bool(okstop), 'sum_ok': bool(ck)})
    res.sort(key=lambda r: r['t'])
    return res


def main():
    sc = Scope(timeout=60)
    for c in [':RUN', ':TRIGger:SWEep AUTO', ':ACQuire:TYPE NORMal', ':CHANnel1:COUPling DC', ':CHANnel1:BWLimit 20M',
              ':CHANnel1:SCALe 4', ':CHANnel1:OFFSet -12', ':TIMebase:MAIN:SCALe 1', ':TIMebase:MAIN:OFFSet 0',
              ':ACQuire:MDEPth 10M']:
        sc.w(c)
    t_end = time.time() + MIN * 60
    n = 0
    while time.time() < t_end:
        time.sleep(1.0)
        sc.w(':RUN')
        time.sleep(10.6)
        sc.w(':STOP')
        tstop = time.time()
        time.sleep(0.5)
        try:
            t, v, dx = sc.read(1, fmt='BYTE')
        except (ConnectionError, OSError) as e:
            print('scope connection lost:', e, flush=True)
            return
        D = max(1, int(round(10e-6 / dx)))
        k = len(v) // D
        vd = v[:k * D].reshape(k, D).mean(1)
        td = t[:k * D:D]
        fr = frames_from(td, vd)
        if any(not r['sum_ok'] for r in fr):
            np.save(time.strftime('data/badsum_%H%M%S.npy'), np.vstack([td, vd]).astype(np.float32))
        with open(OUT, 'a') as f:
            for r in fr:
                r['wall'] = tstop + r['t']
                r['note'] = NOTE
                f.write(json.dumps(r) + '\n')
        n += len(fr)
        print(time.strftime('%H:%M:%S'), ' | '.join(
            f"{r['kind']} {len(r['bytes'])}B {'ok' if r['sum_ok'] else 'BAD'}" for r in fr), flush=True)
    sc.w(':RUN')
    sc.close()
    print('done, frames logged:', n)


if __name__ == '__main__':
    main()
