import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        self.target_heater = None # To be found during Klipper's 'ready' state
        self.captured_fb_pwm = 0.0 # Mutable container to capture PID PWM from the original method
        self.backup_control = None
    
    @abstractmethod
    def compute_control(self, pid_self, read_time, temp, target_temp):
        """Math goes here in the child class"""
        # TODO: remove this class, given we are replacing the whole control object it isn't necessary anymore
        # we can just use the direct function calls and implement our own algorithm propperly.
        pass

    def temperature_update(self, read_time, temp, target_temp):
        """Called by heater to update control logic and set PWM"""
        raise NotImplementedError("temperature_update must be implemented in the child class.")

    def check_busy(self, eventtime, smoothed_temp, target_temp):
        """Return True if heater is still stabilizing (default: False)"""
        return False

    def set_pwm(self, read_time, value):
        """(Optional) Used by autotune routines to override PWM output"""
        pass