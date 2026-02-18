import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        self.target_heater = None # To be found during Klipper's 'ready' state

    def install_hijack(self):
        # 1. Find the actual Klipper heater object
        pheater = self.printer.lookup_object('heaters').lookup_heater(self.heater_name)
        # 2. Find the ControlPID instance inside that heater
        self.target_heater = pheater.cooling_fan.speed_func.__self__ # Common way to grab the PID obj
        
        # 3. Save the original method
        self.orig_temp_update = self.target_heater.temperature_update
        
        # 4. Perform the Monkey Patch
        self.target_heater.temperature_update = self.monkey_patch_update

    def monkey_patch_update(self, pid_self, read_time, temp, target_temp):
        try:
            # We pass pid_self (the ControlPID instance) into the architecture here
            new_pwm = self.compute_control(pid_self, read_time, temp, target_temp)
            new_pwm = max(0.0, min(1.0, new_pwm))  # Clamp between 0 and 1
            pid_self.heater.set_pwm(read_time, new_pwm)
        except Exception as e:
            # Safety Fallback: hand keys back to original PID
            self.orig_temp_update(read_time, temp, target_temp)
            
    @abstractmethod
    def compute_control(self, pid_self, read_time, temp, target_temp):
        """Math goes here in the child class"""
        pass