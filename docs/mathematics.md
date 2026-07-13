# Mathematical Model and Verification

## Modified Nodal Analysis

CircuitCanvas uses Modified Nodal Analysis (MNA) to turn a circuit graph into

\[
Gx(t)+C\dot{x}(t)=b(t).
\]

The ground node is the battery's negative terminal. The unknown vector contains every other node voltage, the battery current, and one auxiliary current for each inductor.

## Component stamps

For a two-terminal component between nodes \(a\) and \(b\), define

\[
S(a,b,y)=
\begin{bmatrix}
+y & -y\\
-y & +y
\end{bmatrix}.
\]

- A resistor contributes \(S(a,b,1/R)\) to \(G\).
- A capacitor contributes \(S(a,b,C)\) to the dynamic matrix \(C\).
- An ideal voltage source adds an incidence row and column to \(G\), with its voltage in \(b\).
- An inductor adds an incidence row and column to \(G\) and \(-L\) on its auxiliary-current diagonal in the dynamic matrix.

Ground-node rows and columns are omitted rather than inserted as zero equations.

## Kirchhoff equations shown in the UI

For every non-reference node, CircuitCanvas reports KCL using signed branch currents:

\[
\sum_{e\in\delta(n)} s_{n,e} i_e(t)=0.
\]

It builds a fundamental cycle basis on the component multigraph and reports one independent KVL equation per cycle:

\[
\sum_{e\in\mathcal{C}} s_{\mathcal{C},e} v_e(t)=0.
\]

Parallel edges are preserved, so a two-edge loop is represented correctly. Every equation shows its symbolic form, signed numeric substitution at the selected time, and the computed residual. The differential view prints the R/C/L constitutive equations and the exact MNA descriptor matrices.

## Time integration

The battery is treated as a step from 0 V to the configured value. With a fixed step \(\Delta t\), the implicit trapezoidal update is

\[
\left(G+\frac{2C}{\Delta t}\right)x_{k+1}
=\left(\frac{2C}{\Delta t}-G\right)x_k+b_{k+1}+b_k.
\]

The left-hand matrix remains constant for a linear circuit and fixed time step, so its LU factorization is reused. Backward Euler is available through

\[
\left(G+\frac{C}{\Delta t}\right)x_{k+1}
=\frac{C}{\Delta t}x_k+b_{k+1}.
\]

## Reported quantities

Voltage is defined from each component's `node_a` to `node_b`. Current follows the same passive reference direction.

\[
i_R=\frac{v_R}{R},\qquad
i_C=C\frac{dv_C}{dt},\qquad
v_L=L\frac{di_L}{dt}.
\]

Instantaneous passive power is

\[
p(t)=v(t)i(t).
\]

Reactive stored energy is

\[
E_C=\frac{1}{2}Cv_C^2,\qquad
E_L=\frac{1}{2}Li_L^2.
\]

The source current uses the MNA auxiliary-current direction. A negative source power means the battery is delivering energy to the network; the user-facing summary reports delivered magnitude.

## Current arrows on ideal wires

MNA solves branch currents through physical elements, not an arbitrary current for every zero-resistance drawing segment. CircuitCanvas converts those solved terminal currents into wire arrows by solving

\[
Bf=-q,
\]

where `B` is the oriented incidence matrix of each connected wire network, `q` is the vector of solved terminal injections, and `f` contains displayed wire currents. The least-norm solution is deterministic and satisfies KCL at every junction. Its residual is tested independently.

The arrow direction follows the sign of `f`; speed increases logarithmically with magnitude and arrows stop when the current is numerically zero or the simulation result is stale. In a closed loop made only of ideal wire, several segment-current assignments are physically equivalent, so the least-norm result is a visualization convention rather than an extra physical claim.

## Analytical verification

The automated suite compares simulated curves with closed forms.

For RC charging:

\[
v_C(t)=V\left(1-e^{-t/(RC)}\right).
\]

For an RL step:

\[
i_L(t)=\frac{V}{R}\left(1-e^{-Rt/L}\right).
\]

Additional fixtures cover resistor-only DC behavior, underdamped RLC response, backward Euler, finite results, matrix residuals, KCL/KVL consistency, and reactive energy.

Numerical tolerances scale with the selected step size. The tests deliberately compare physical behavior rather than implementation details.
