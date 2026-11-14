# 3D Near-to-Far-Field Transform - Theory Engineer specification

Verbatim record of the Theory Engineer dispatch received for E13. Do not edit
without a new ruling; the formulas below are normative.

## 1. The formula

    E_far(r) = (j k e^{-j k r}) / (4 pi r) *
               [ eta_0 * rhat x (rhat x J_tilde) + rhat x M_tilde ]

where

    J_tilde(rhat) = integral over S of  J_s(r') e^{j k rhat . r'} dS'
    M_tilde(rhat) = integral over S of  M_s(r') e^{j k rhat . r'} dS'

## 2. Quadrature

Do not use raw trapezoidal. Use the midpoint patch rule over the physical
surface patches. Interpolate the tangential E and H fields to the patch
centers, apply the outward normal cross products, multiply by the patch area
A_q, and apply the phase factor e^{j k rhat . r_q}.

## 3. Angles

Use the standard spherical basis: rhat from +Z, phi from +X. Report E_theta and
E_phi.

## 4. Gain

    U(theta, phi) = (r^2 / (2 eta_0)) * (|E_theta|^2 + |E_phi|^2)
    D = 4 pi U / P_rad
    G = 4 pi U / P_in
