# Proactive Power Compensation Control

General Description
---

Control Law
---
U = U_fb + U_ff

U_ff = T_sp * K_ss + P_fan * K_fan + e_velocity * K_flow

Features and Characteristics
---

Calibration Details
---

Notes and Additional Reading
---
This architecture does a couple key things right. 
1. It supplies steady-state power proportional to temperature setpoint. 
2. It adds/subtracts additional power control action proactively to cancel measureable disturbances. (part cooling fan, ambient temperature, proximity to heated bed, material flow)
3. It uses state-based switching logic to ensure time-optimal transient behavior.
4. It uses the existing PID class to reject disturbances. 
5. It is easy to auto-calibrate and builds a readable Look-Up-Table (LUT) essentially an expected power draw profile for different machine operating conditions.
6. It is nonlinear and makes few assumptions about the heater dynamics.

References
---
