
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
- [x] Ensure that thermal runaway still is triggered
- [x] Test the custom Calibration algorithm --> will it run
- [x] Test the custom Calibration algorithm --> How is the performance

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

- [x] Add support for additional control architectures, port MPC from Kalico
    - [x] MPC from kalico ported over -- (calibration works, required monkeypatch of heater.wait_while function, heater.get_status['power'] is in ratio not wattage --> fixed in calibration script)
    - [x] Removed the "profile" object used to initate the class, passing standard config instead. --> This might be worth revisiting. Making profile support optional
- [ ] Add a look-ahead class which tracks arbitrary states. Such as future fan control speeds, temperature and flow rate.
- [x] HIGH PRIORITY: Look at the timing of object_lookups in the controller objects. I want to get rid of the necessity to run a post_init script.
    - MPC kalico implementation does this with a if toolhead is None: object_lookup['toolhead'] type structure. Both post-init and try if none seem like sub optimal ways to handle this. --> after some research it might be solveable using a "Lazy Property Pattern" @property def heater(self): if self._heater is None: self._heater = printer.lookup_object("heater_name"); return self._heater --> the heater method behaves like an attribute which self-initializes if value is None. 
    Alternitavely 3.8+ python with functools has the cached_property decorator which simplifies implementation:
    @cached_property
    def heater(self):
        return self.lookup_object("heater_name") --> This does the same, but if the objects change without the control-class being renewed the values aren't automatically refound like in the strict @property manor.
</details>
