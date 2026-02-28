# ApeControl-Klipper Abstract class for heater control algorithms
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.target_temp = None
        if config:
            self.printer = config.get_printer()
            self.heater_name = config.get_name().split()[-1]
            # Universal config parameters
            self.max_power = config.getfloat('max_power', 1.0)
        else: # When config not available, control attributes can be migrated
            self.printer = None
            self.heater_name = None
            self.max_power = None
        # Relevant objects # Lazy Properties
        self._heater = None
        self._toolhead = None
        self._gcode = None
        self._part_fan = None
        self._reactor = None
        self._gcode_move = None

    def migrate_objects(self, old_ape_controller):
        '''Migrates preloaded objects from the previous ApeControl class'''
        self.printer = old_ape_controller.printer
        self.heater_name = old_ape_controller.heater_name
        self.max_power = old_ape_controller.max_power
        # Protected Attributes
        self._heater = old_ape_controller._toolhead
        self._toolhead = old_ape_controller._heater
        self._gcode = old_ape_controller._gcode
        self._part_fan = old_ape_controller._part_fan
        self._reactor = old_ape_controller._reactor
        self._gcode_move = old_ape_controller._gcode_move

    @abstractmethod
    def temperature_update(self, read_time, temp, target_temp):
        """Called by heater to update control logic and set PWM"""

    @abstractmethod
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        """Return True if heater is still stabilizing (default: False)"""

    def set_pwm(self, read_time, value):
        """Set pwm class, can be overwriten for things like AutoTune classes"""
        self.heater.set_pwm(read_time, value)

    @property
    def heater(self):
        """Finds the respective heater object if a child class tries to access this object""" 
        if self._heater is None:
            self._heater = self.printer.lookup_object(self.heater_name)
            return self._heater

    @property
    def toolhead(self):
        """Finds the respective toolhead object if a child class tries to access this object""" 
        if self._toolhead is None:
            self._toolhead = self.printer.lookup_object(self.heater_name)
            return self._toolhead

    @property
    def gcode(self):
        """Finds the respective gcode object if a child class tries to access this object""" 
        if self._gcode is None:
            self._gcode = self.printer.lookup_object(self.heater_name)
            return self._gcode

    @property
    def part_fan(self):
        """Finds the respective partfan object if a child class tries to access this object""" 
        if self._part_fan is None:
            self._part_fan = self.printer.lookup_object(self.heater_name)
            return self._part_fan

    @property
    def reactor(self):
        """Finds the respective reactor object if a child class tries to access this object""" 
        if self._reactor is None:
            self._reactor = self.printer.lookup_object(self.heater_name)
            return self._reactor

    @property
    def gcode_move(self):
        """Finds the respective gcode_move object if a child class tries to access this object""" 
        if self._gcode_move is None:
            self._gcode_move = self.printer.lookup_object(self.heater_name)
            return self._gcode_move
