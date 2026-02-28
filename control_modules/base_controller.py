# ApeControl-Klipper Abstract class for heater control algorithms
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, apeconfig):
        self.config_params = apeconfig
        self.printer = apeconfig.printer # This is a bit of an inefficiency still
        self.reactor = self.printer.get_reactor()
        self.target_temp = None
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        # Lazy attributes
        self._gcode = None
        self._toolhead = None

    def handle_ready(self):
        # Load Critical objects
        self.heater = self.printer.lookup_object('heaters').lookup_heater(self.config_params.heater_name)

    @abstractmethod
    def temperature_update(self, read_time, temp, target_temp):
        """Called by heater to update control logic and set PWM"""
        pass

    @abstractmethod
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        """Return True if heater is still stabilizing (default: False)"""
        pass

    def set_pwm(self, read_time, value):
        """Can be e overwriten for things like AutoTune classes"""
        self.heater.set_pwm(read_time, value)

    @property
    def gcode(self):
        if self._gcode is None:
            self._gcode = self.printer.lookup_object('gcode')
        return self._gcode
    
    @property
    def toolhead(self):
        if self._toolhead is None:
            self._toolhead = self.printer.lookup_object('toolhead')
        return self._toolhead