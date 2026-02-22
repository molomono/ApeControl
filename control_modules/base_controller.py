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
        pass