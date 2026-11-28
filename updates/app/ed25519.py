"""Ed25519 (RFC 8032) in pure Python, standard library only. Used to sign (tool) and verify (program) license keys."""
import hashlib
p = 2**255 - 19
q = 2**252 + 27742317777372353535851937790883648493
d = -121665 * pow(121666, p - 2, p) % p
I = pow(2, (p - 1) // 4, p)
def _inv(x): return pow(x, p - 2, p)
def _xrecover(y):
    xx = (y * y - 1) * _inv(d * y * y + 1)
    x = pow(xx, (p + 3) // 8, p)
    if (x * x - xx) % p != 0: x = (x * I) % p
    if x % 2 != 0: x = p - x
    return x
By = 4 * _inv(5); Bx = _xrecover(By); B = (Bx % p, By % p, 1, (Bx * By) % p)
def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % p; Bb = (P[1] + P[0]) * (Q[1] + Q[0]) % p
    C = 2 * P[3] * Q[3] * d % p; D = 2 * P[2] * Q[2] % p
    E, F, G, H = Bb - A, D - C, D + C, Bb + A
    return (E * F % p, G * H % p, F * G % p, E * H % p)
def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1: Q = _add(Q, P)
        P = _add(P, P); s >>= 1
    return Q
def _enc(P):
    zi = _inv(P[2]); x = P[0] * zi % p; y = P[1] * zi % p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")
def _dec(s):
    y = int.from_bytes(s, "little"); sign = y >> 255; y &= (1 << 255) - 1
    x = _xrecover(y)
    if (x & 1) != sign: x = p - x
    P = (x, y, 1, x * y % p)
    if (-P[0] * P[0] + P[1] * P[1] - 1 - d * P[0] * P[0] * P[1] * P[1]) % p != 0: raise ValueError("bad point")
    return P
def _H(m): return hashlib.sha512(m).digest()
def _clamp(h):
    a = int.from_bytes(h[:32], "little"); a &= (1 << 254) - 8; a |= 1 << 254; return a
def public_key(seed):
    return _enc(_mul(_clamp(_H(seed)), B))
def sign(seed, msg):
    h = _H(seed); a = _clamp(h); A = _enc(_mul(a, B))
    r = int.from_bytes(_H(h[32:] + msg), "little") % q
    R = _enc(_mul(r, B))
    k = int.from_bytes(_H(R + A + msg), "little") % q
    return R + ((r + k * a) % q).to_bytes(32, "little")
def verify(pub, msg, sig):
    try:
        if len(sig) != 64 or len(pub) != 32: return False
        A = _dec(pub); R = _dec(sig[:32]); S = int.from_bytes(sig[32:], "little")
        if S >= q: return False
        k = int.from_bytes(_H(sig[:32] + pub + msg), "little") % q
        L = _mul(S, B); Rr = _add(R, _mul(k, A))
        return _enc(L) == _enc(Rr)
    except Exception: return False
