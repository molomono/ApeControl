import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        self.target_heater = None # To be found during Klipper's 'ready' state
        self.captured_fb_pwm = 0.0 # Mutable container to capture PID PWM from the original method

    def install_hijack(self):
        # 1. Find the actual Klipper heater object
        pheater = self.printer.lookup_object('heaters').lookup_heater(self.heater_name)
        # 2. Find the ControlPID instance inside that heater
        self.target_heater = pheater.control
        
        # 3. Save the original method
        self.orig_temp_update = self.target_heater.temperature_update
        
        # 4. Perform the Monkey Patch
        self.target_heater.temperature_update = lambda read_time, temp, target_temp: self.monkey_patch_update(self.target_heater, read_time, temp, target_temp)

        # 5. TODO: Overwrite PID values... (this is to allow the original PID controller to remain configured as a backup if we retune PID after FF compensation)

    def monkey_patch_update(self, pid_self, read_time, temp, target_temp):
        try:
            # Store the original set_pwm method for later
            self.real_set_pwm = pid_self.heater.set_pwm

            # Override set_pwm to capture the PID's computed PWM value without sending it to the heater
            def dummy_set_pwm(tm, value):
                self.captured_fb_pwm = value
            pid_self.heater.set_pwm = dummy_set_pwm

            # We pass pid_self (the ControlPID instance) into the architecture here
            new_pwm = self.compute_control(pid_self, read_time, temp, target_temp)
            new_pwm = max(0.0, min(1.0, new_pwm))  # Clamp between 0 and 1
            
            # Restore the original set_pwm and set the Pwm
            pid_self.heater.set_pwm = self.real_set_pwm
            pid_self.heater.set_pwm(read_time, new_pwm)

        except Exception as e:
            logging.info("Error in compute_control: %s. Falling back to original PID." % str(e))
            # TODO: PID values can be overwritten with ApeControl module, restore original PID behavior before handing it back to the original function.

            # Safety Fallback: hand keys back to original PID
            pid_self.heater.set_pwm = self.real_set_pwm # Remove the dummy function, makes the heater-set_pwm function write to the heater again
            self.orig_temp_update(read_time, temp, target_temp) # Call original PID logic
            

    @abstractmethod
    def compute_control(self, pid_self, read_time, temp, target_temp):
        """Math goes here in the child class"""
        pass