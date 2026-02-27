# ApeControl
A control systems extension for mainbranch Klipper.

Overview and Motivation
--- 
ApeControl is a collection of alternative control algorithms for heaters in klipper. Motivated by the desire to improve setpoint transients and regulation beyond PID control lead to ApeControl.

There are two primary components that make up this extension. 
- A dynamic loader which is used to select the desired control algorithm using the printer.cfg file.
- An abstract class which provides access to necessary objects and methods for klipper to treat any new control class the same as the natively supported Watermark (bangbang) and ControlPID classes.

How it works
---
ApeControl acts as a control bridge. It waits for the original control object to load before swapping it out with custom "Control Architectures" these custom classes may calculate the input power to heater objects based on real-time printer state, physics-informed models, predictive observers/modeling and so forth.

Key Features
---
* **Non-Destructive Integration**: Injects custom logic at runtime. No modifications to Klipper’s core source files are required.

* **Modular Architecture**: Swap between different control logic (e.g., standard PID, FFC+PID, MPX) via simple configuration changes.

* **Safety Fallback**: Klipper's built-in exception handling ensures that if unexpected thermal behaior occurs the existing fail safes kick in.

* **Expand and Expriment**: Designed to be a development sandbox. The framework abstracts away the complexity of Klipper’s internal bindings, making it easier for hobbyists to prototype and test new heater control algorithms. 

* **--todo: New Control Module Tutorial**

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
```
[ape_control extruder]  # ape_control loads the dynamic loader, 'extruder' passes the name of the heater object. 'heater_bed' is another classic name.

architecture: pp_control# Selects control_modules/pp_control.py
# This is all that is neccesary to load your desired controller.

# Optional: Custom controller parameters:
k_ss: 0.0012            # Steady-state gain (PWM % per degree K)
k_fan: 0.10             # PWM % additional power draw when fan is max speed.
```
Some modules may have calibration scripts. To tune your controller run the appropriate calibration script. For this example run:
```
PP_CALIBRATE HEATER=extruder Target=200
CONFIG_SAVE # to save the calibrated parameters
```


Control Architectures
---
|Controller Name|Architecture|Feed Forward/Back|Status|Auto-Cal|Description|
|---|---|---|---|---|---|
|Proportional Integral Derivative|pid_control|FB|Complete|Yes|Standard feedback control class in klipper.|
|Proactive Power Control|pp_control|FF+FB|Beta|Yes|Hybrid Steady-state feedforward + Feedback control with switching logic.|
|Model Predictive Control|mpc|FF+FB|Ported From Kalico|Yes|Model-predictive control alogirthm. Simulates future thermal behavior and optimizes control action.|


### Quick side note on hybrid feedback-feedforward control:
Feedback controllers and feedforward controllers can be combined for hybrid control strategies. This generally comes with some benefits including faster transients (settling times), lower overshoot, and more responsive disturbance rejection. 

Although not implemented at this time, a modular structure ff+fb class that allows choosing and tuning FF and FB control algorithms from the printer.cfg file is a future goal. I would rather provide users too much power than too little, this does come with risks.

Disclaimer
---
### ApeControl involves the manipulation of heater safety logic. 

While the framework includes safety fallbacks, it is intended for users who have experience with 3D printers and control tuning. 

**Always monitor your printer after installing new control architectures and ensure your max_temp and verify_heater settings are correctly configured in Klipper.**

---
License: GPL-3.0