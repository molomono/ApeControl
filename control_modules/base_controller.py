import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        self.target_heater = None # To be found during Klipper's 'ready' state
 
    @abstractmethod
    def temperature_update(self, read_time, temp, target_temp):
        """Called by heater to update control logic and set PWM"""
        pass
    @abstractmethod
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        """Return True if heater is still stabilizing (default: False)"""
        pass
    @abstractmethod
    def set_pwm(self, read_time, value):
        """(Optional) Used by autotune routines to override PWM output"""
        pass