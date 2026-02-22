
# ApeControl Project Notes

>This document tracks technical observations, compatibility strategies, and actionable TODOs for the ApeControl control modules lab for Klipper 3D printer software. Use the checklists to expand/collapse as tasks are added or completed.

---

## 1. Legacy Code Observations
<details>
<summary>Checklist: Inefficiencies, design issues, or technical debt found while reading legacy code</summary>

- [ ] The PID Calibration object is loaded irregardless of algorithm choice. (in heaters.py)
- [ ] Document any hardcoded values or magic numbers:
    - algos: dict in heaters.py
    - printer.load_object(config,'pid_calibrate') in heaters.py
- [ ] --Testing, but there seems to be an unneccesary call of self.calc_pid in the calibrate_pid.py file

</details>

## 2. Compatibility & Dynamic Loading
<details>
<summary>Checklist: Solutions for maintaining compatibility and enabling runtime module loading</summary>

-  Ensure dynamic import logic: see ape_control.py, which loads the correct control module (and calibration object).
- [ ] Maintain backup of original control object for safe fallback (see `exchange_controller`)
- [x] Change the original monkey-patch of the update script to an actual heater.control module swap. see 3.

## 2.B Tests and validation 
- [ ] Ensure that the control fallback works
- [ ] Ensure that thermal runaway still is triggered
- [x] Test the custom Calibration algorithm --> will it run
- [ ] Test the custom Calibration algorithm --> How is the performance

</details>

## 3. Current Porting & Monkey Patch Refactor
<details>
<summary>Checklist: Porting the monkey patch updating algorithm to mimic AutoTune's controller swap</summary>

- [ ] Refactor controller exchange to store and restore original control safely
- [x] Make monkey patch logic deprecated
- [x] Remove or refactor `install_hijack` as needed (see comments in `ape_control.py`)
- [ ] Implement safety logic to trigger backup controller if new one fails
- [x] Ensure compatibility with both legacy and new control architectures

</details>

## 4. Functional Roadmap TODOs
<details>
<summary>Checklist: Features and milestones for the control modules lab</summary>

- [ ] Add support for additional control architectures (e.g., MPC, lead-lag)
- [ ] Add a look-ahead class which tracks arbitrary states. Such as future fan control speeds, temperature and flow rate.

</details>
