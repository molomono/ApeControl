# ApeControl-Klipper Abstract class for heater control algorithms
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        self.target_heater = None # To be found during Klipper's 'ready' state
        self.target_temp = None
        # Relevant objects
        self.heater = None
        self.heater_max_power = config.getfloat('max_power', 1.0)
        
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def handle_ready(self):
        self.heater = self.printer.lookup_object('heaters').lookup_heater(self.heater_name)

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
        """Can be e overwriten for things like AutoTune classes"""
        pass
    '''
    def set_pwm(self, read_time, value): # simplest form, place inside your control class
        self.heater.set_pwm(read_time, value)
        
    '''