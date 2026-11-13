"""Placa retangular delgada (Kirchhoff) por elementos finitos — laje com borda livre.

Usada no muro com contrafortes: o painel da cortina entre dois contrafortes é uma
laje engastada na sapata e contínua sobre os contrafortes (3 bordas engastadas),
com a borda superior LIVRE; o mesmo vale para a base entre contrafortes.

Elemento retangular de 4 nós e 12 graus de liberdade (Adini-Clough-Melosh),
espessura constante, ν = 0,2 (NBR 6118). Carga variando só ao longo de y.

Convenção: carga e flecha positivas no mesmo sentido; momento POSITIVO traciona a
face oposta à carga (meio do vão), NEGATIVO traciona a face carregada (engastes).
``Mx`` flete na direção x (armadura paralela a x), ``My`` na direção y.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

ENGASTE, APOIO, LIVRE = "E", "A", "L"
NU = 0.2


def _base(x, y):
    """Os 12 monômios do elemento e suas derivadas: (P, Px, Py, Pxx, Pyy, Pxy)."""
    o, z = np.ones_like(x), np.zeros_like(x)
    P = [o, x, y, x**2, x * y, y**2, x**3, x**2 * y, x * y**2, y**3, x**3 * y, x * y**3]
    Px = [z, o, z, 2 * x, y, z, 3 * x**2, 2 * x * y, y**2, z, 3 * x**2 * y, y**3]
    Py = [z, z, o, z, x, 2 * y, z, x**2, 2 * x * y, 3 * y**2, x**3, 3 * x * y**2]
    Pxx = [z, z, z, 2 * o, z, z, 6 * x, 2 * y, z, z, 6 * x * y, z]
    Pyy = [z, z, z, z, z, 2 * o, z, z, 2 * x, 6 * y, z, 6 * x * y]
    Pxy = [z, z, z, z, o, z, z, 2 * x, 2 * y, z, 3 * x**2, 3 * y**2]
    return [np.stack(v, axis=-1) for v in (P, Px, Py, Pxx, Pyy, Pxy)]


@dataclass(frozen=True)
class Placa:
    lx: float
    ly: float
    x: np.ndarray        # (nx+1,)
    y: np.ndarray        # (ny+1,)
    Mx: np.ndarray       # (ny+1, nx+1) kN·m/m
    My: np.ndarray
    Vx0: np.ndarray      # reação por metro na borda x = 0, em cada y (kN/m); nan nos cantos
    Vx1: np.ndarray
    Vy0: np.ndarray      # reação por metro na borda y = 0, em cada x
    Vy1: np.ndarray
    carga_total: float
    reacao_total: float


@lru_cache(maxsize=256)
def resolver(lx: float, ly: float, carga: tuple[float, ...], bordas: tuple[str, str, str, str] = (
        ENGASTE, ENGASTE, ENGASTE, LIVRE), nx: int = 14, nu: float = NU) -> Placa:
    """Resolve a placa ``lx × ly``.

    ``carga``: pressão (kPa) em ny+1 alturas igualmente espaçadas de y = 0 a y = ly
    (interpolação linear entre elas). ``bordas``: condição em (x = 0, x = lx, y = 0, y = ly).
    """
    ny = len(carga) - 1
    a, b = lx / nx, ly / ny
    nos = np.array([(0.0, 0.0), (a, 0.0), (a, b), (0.0, b)])
    P, Px, Py, *_ = _base(nos[:, 0], nos[:, 1])
    C = np.empty((12, 12))
    C[0::3], C[1::3], C[2::3] = P, Px, Py          # g.d.l. por nó: w, ∂w/∂x, ∂w/∂y
    A = np.linalg.inv(C)
    g, wg = np.polynomial.legendre.leggauss(4)
    xg, yg = np.meshgrid((g + 1) * a / 2, (g + 1) * b / 2)
    wgt = (np.outer(wg, wg) * a * b / 4).ravel()
    Pg, _, _, Pxx, Pyy, Pxy = _base(xg.ravel(), yg.ravel())
    N = Pg @ A                                      # (16, 12)
    B = np.stack([Pxx @ A, Pyy @ A, 2 * Pxy @ A], axis=1)       # (16, 3, 12)
    Dm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    Ke = np.einsum("g,gik,ij,gjl->kl", wgt, B, Dm, B)
    eta = yg.ravel() / b                            # posição relativa em y no elemento

    n_nos = (nx + 1) * (ny + 1)
    K = np.zeros((3 * n_nos, 3 * n_nos))
    f = np.zeros(3 * n_nos)
    conec = []
    p = np.asarray(carga, float)
    for j in range(ny):
        fe = N.T @ (wgt * (p[j] * (1 - eta) + p[j + 1] * eta))
        for i in range(nx):
            n0 = j * (nx + 1) + i
            ids = [n0, n0 + 1, n0 + nx + 2, n0 + nx + 1]
            gl = np.array([3 * k + d for k in ids for d in range(3)])
            K[np.ix_(gl, gl)] += Ke
            f[gl] += fe
            conec.append(gl)

    preso = np.zeros(3 * n_nos, bool)
    ii, jj = np.meshgrid(np.arange(nx + 1), np.arange(ny + 1))
    no = (jj * (nx + 1) + ii)
    for cond, mascara, normal in ((bordas[0], ii == 0, 1), (bordas[1], ii == nx, 1),
                                  (bordas[2], jj == 0, 2), (bordas[3], jj == ny, 2)):
        if cond == LIVRE:
            continue
        k = no[mascara]
        preso[3 * k] = True                         # w = 0
        preso[3 * k + (3 - normal)] = True          # derivada tangencial = 0
        if cond == ENGASTE:
            preso[3 * k + normal] = True            # derivada normal = 0
    livre = ~preso
    u = np.zeros(3 * n_nos)
    u[livre] = np.linalg.solve(K[np.ix_(livre, livre)], f[livre])
    R = K @ u - f

    # momentos nos nós (média dos elementos vizinhos)
    _, _, _, Pxx_n, Pyy_n, _ = _base(nos[:, 0], nos[:, 1])
    Bxx, Byy = Pxx_n @ A, Pyy_n @ A                 # (4, 12)
    Mx = np.zeros(n_nos)
    My = np.zeros(n_nos)
    cont = np.zeros(n_nos)
    for gl in conec:
        kxx, kyy = Bxx @ u[gl], Byy @ u[gl]
        ids = gl[0::3] // 3
        Mx[ids] += -(kxx + nu * kyy)
        My[ids] += -(kyy + nu * kxx)
        cont[ids] += 1
    Mx, My = (Mx / cont).reshape(ny + 1, nx + 1), (My / cont).reshape(ny + 1, nx + 1)

    Rw = -R[0::3].reshape(ny + 1, nx + 1)           # força de reação (positiva contra a carga)
    tx = np.full(nx + 1, a)
    ty = np.full(ny + 1, b)
    tx[[0, -1]] = np.nan
    ty[[0, -1]] = np.nan                            # cantos: reação repartida entre duas bordas

    def borda(cond, valores, trib):
        return valores / trib if cond != LIVRE else np.zeros_like(valores)
    carga_total = float(sum((p[j] + p[j + 1]) / 2 * b for j in range(ny)) * lx)
    return Placa(lx, ly, np.linspace(0, lx, nx + 1), np.linspace(0, ly, ny + 1), Mx, My,
                 borda(bordas[0], Rw[:, 0], ty), borda(bordas[1], Rw[:, -1], ty),
                 borda(bordas[2], Rw[0, :], tx), borda(bordas[3], Rw[-1, :], tx),
                 carga_total, float(Rw[preso[0::3].reshape(ny + 1, nx + 1)].sum()))


def classificar(lx: float, ly: float) -> tuple[float, str]:
    """Razão entre os vãos e o comportamento esperado do painel com a borda ``y = ly`` livre."""
    r = ly / lx
    if r > 2:
        return r, ("painel alto (altura > 2·vão): trabalha principalmente na horizontal, entre os contrafortes; "
                   "junto à base ainda flete na vertical")
    if r < 0.5:
        return r, ("painel largo (vão > 2·altura): no meio do vão trabalha principalmente como balanço vertical; "
                   "junto aos contrafortes flete na horizontal")
    return r, "laje armada nas duas direções, com três bordas engastadas e a borda superior livre"
