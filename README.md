# ApeControl
Monkey-patched control extensions for Klipper heater classes.


---
ApeControl is a modular control framework for Klipper that enables the injection of advanced control architectures into the native heater logic. By utilizing "monkey-patching" techniques, ApeControl intercepts Klipper's internal ControlPID methods, allowing users to implement sophisticated thermal control strategies—such as Feedforward, Lead-Lag compensation, and Predictive Power Control—without forking the Klipper mainbranch.

Overview and Motivation
---
Klipper’s native thermal management is built around a standard PID (Proportional-Integral-Derivative) loop. While robust, this architecture is reactive and often struggles with changing tempearture setpoints and significant disturbances like high-flow extrusion or aggressive part-cooling fans.

ApeControl acts as a control bridge. It hijacks the hardware command stream to allow custom "Control Architectures" to calculate the input power to heater objects based on real-time printer state, physics-informed models, predictive observers and so forth.

Key Features
---
* **Non-Destructive Integration**: Injects custom logic at runtime. No modifications to Klipper’s core source files are required.

* **Modular Architecture**: Swap between different control logic (e.g., standard PID, FFC+PID, MRAC) via simple configuration changes.

* **Safety Fallback**: Klipper's built-in exception handling ensures that if unexpected thermal behaior occurs the existing fail safes kick in.

* **Expand and Expriment**: Designed as a development sandbox. The framework abstracts away the complexity of Klipper’s internal bindings, making it easier for hobbyists to prototype and test new heater control algorithms. **--todo: New Control Module Tutorial**

Installation
---
1. Clone this repository to your Klipper host device.
2. Make install.sh executable and run it.

```bash
git clone https://github.com/molomono/ApeControl.git
cd ./ApeControl
chmod +x install.sh && ./install.sh
```
Configuration
--- 
To enable ApeControl, define the module in your printer.cfg. You can specify the architecture and provide the necessary parameters for that specific module. 
```toml
[ape_control extruder]
architecture: pp_control# Selects control_modules/pp_control.py
k_ss: 0.0012            # Steady-state gain (PWM % per degree)
t_overshoot: 8.5        # Thermal momentum offset (Degrees)
t_coast_time: 5.0       # Time until thermal momentum is 0 (seconds)
k_flow: 0.02            # Volumetric flow compensation (PWM % per mm/s)
k_fan: 0.10             # PWM % additional power draw when fan is max speed.
```
Some modules have calibration scripts, others are tuned by hand. See the controller specific documentation for more information.

Control Architectures
---
|Controller Name|Architecture|Feed Forward/Back|Status|Auto-Cal|Description|
|---|---|---|---|---|---|
|Proportional Integral Derivative|pid|FB|Complete|Yes|Standard feedback control class in klipper.|
|Proactive Power Control|pp_control|Both|Beta|WIP|Hybrid Steady-state feedforward + Feedback control with switching logic.|
|Lead-Lag Compensator|llc|FF|Planned|No|Phase-lead compensation to improve transient response and stability.|
|Model Reference Adaptive|mrac|Both|Planned|No|Real-time parameter adjustment to match a defined reference model.|
|Disturbance Observer|dob|FB|Planned|No|Actively estimates and cancels external loads (fan/flow) in real-time.|
|Fuzzy Logic Controller|flc|FB|Planned|No|Rule-based non-linear control for complex thermal environments.|


### Quick side note on hybrid feedback-feedforward control:
Feedback controllers and feedforward controllers can be combined for hybrid control strategies. This generally comes with some benefits including faster transients (settling times), lower overshoot, and more responsive disturbance rejection. This also is the fundimental motivation underpinning this repository. Giving birth to the original PP-Control architecture, which combines Feed-Forward Compensation in the form of Proactive Power adjustments. In addition to the Monkey-Patch abstraction layer which makes developing new control algorithms for klipper a relatively simple endeavor. 

Although not implemented at this time, a modular structure that allows choosing and tuning FF and FB control algorithms from the printer.cfg file is a desireable direction. I would rather provide users too much power than too little, this does come with risks and keep that in mind.

Disclaimer
---
### ApeControl involves the manipulation of heater safety logic. 

While the framework includes safety fallbacks, it is intended for users who have experience with 3D printers and control tuning. 

**Always monitor your printer after installing new control architectures and ensure your max_temp and verify_heater settings are correctly configured in Klipper.**

---
License: GPL-3.0