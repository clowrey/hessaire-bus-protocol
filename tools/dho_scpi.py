"""Small SCPI helper for the DHO804 (NKmod). Import: from dho_scpi import Scope
The scope address comes from the ip argument or the DHO_IP environment variable."""
import os, socket, time
import numpy as np


class Scope:
    def __init__(self, ip=None, port=5555, timeout=30):
        ip = ip or os.environ.get('DHO_IP')
        if not ip:
            raise ValueError('Set the DHO_IP environment variable to the scope address, or pass ip=')
        self.s = socket.create_connection((ip, port), timeout=timeout)
        self.buf = bytearray()

    def w(self, cmd, pause=0.12):
        self.s.sendall((cmd + '\n').encode())
        time.sleep(pause)

    def _line(self):
        while b'\n' not in self.buf:
            d = self.s.recv(65536)
            if not d:
                raise EOFError
            self.buf += d
        i = self.buf.index(b'\n')
        line, self.buf = bytes(self.buf[:i]), self.buf[i + 1:]
        return line.decode(errors='replace').strip()

    def q(self, cmd):
        self.s.sendall((cmd + '\n').encode())
        return self._line()

    def _block(self):
        while len(self.buf) < 2:
            self.buf += self.s.recv(65536)
        nd = int(chr(self.buf[1]))
        while len(self.buf) < 2 + nd:
            self.buf += self.s.recv(65536)
        n = int(self.buf[2:2 + nd])
        need = 2 + nd + n + 1
        while len(self.buf) < need:
            self.buf += self.s.recv(min(1 << 20, need - len(self.buf)))
        d = bytes(self.buf[2 + nd:2 + nd + n])
        self.buf = self.buf[need:]
        return d

    def read(self, ch, mode='RAW', npts=None, chunk=1000000, fmt='BYTE'):
        """Read channel ch from the stopped acquisition. Returns (t, v, dx).
        NKmod quirk: the preamble (and :WAVeform:POINts?) reports 22000 points even when the
        record is much longer, so by default read up to :ACQuire:MDEPth? and stop on a short chunk.
        fmt='WORD' reads 16-bit samples (full ADC resolution) instead of 8-bit."""
        self.w(f':WAVeform:SOURce CHANnel{ch}')
        self.w(f':WAVeform:MODE {mode}')
        self.w(f':WAVeform:FORMat {fmt}')
        width = 2 if fmt == 'WORD' else 1
        pre = self.q(':WAVeform:PREamble?').split(',')
        dx, xorig = float(pre[4]), float(pre[5])
        yinc, yorig, yref = float(pre[7]), float(pre[8]), float(pre[9])
        if npts is None:
            npts = int(pre[2])
            if mode == 'RAW':
                try:
                    npts = max(npts, int(float(self.q(':ACQuire:MDEPth?'))))
                except ValueError:
                    pass
        raw = bytearray()
        st = 1
        while st <= npts:
            sp = min(st + chunk - 1, npts)
            self.w(f':WAVeform:STARt {st}', 0.05)
            self.w(f':WAVeform:STOP {sp}', 0.05)
            self.w(':WAVeform:DATA?', 0)
            d = self._block()
            raw += d
            if len(d) < (sp - st + 1) * width:
                break
            st = sp + 1
        dtype = '<u2' if width == 2 else np.uint8
        raw = bytes(raw[:len(raw) - len(raw) % width])
        v = (np.frombuffer(raw, dtype=dtype).astype(float) - yorig - yref) * yinc
        t = np.arange(len(v)) * dx + xorig
        return t, v, dx

    def acquire(self, seconds):
        self.w(':RUN')
        time.sleep(seconds)
        self.w(':STOP')
        time.sleep(0.4)

    def close(self):
        self.s.close()
