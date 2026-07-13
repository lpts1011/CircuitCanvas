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
