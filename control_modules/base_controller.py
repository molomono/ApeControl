import logging
from abc import ABC, abstractmethod

class BaseController(ABC):
    def __init__(self, config, pid_self):
        self.printer = config.get_printer()
        self.pid_self = pid_self
        self.heater_name = config.get_name().split()[-1]
        self.max_power = config.getfloat('max_power', 1.0, minval=0.0, maxval=1.0)
        
        # Internal state for monkey-patch capture
        self._captured_pid_pwm = 0.0
        
        # Initialize Monkey-Patch
        self._setup_hijack()

    def _setup_hijack(self):
        # 1. Store the original methods
        self.orig_temp_update = self.pid_self.temperature_update
        self.orig_set_pwm = self.pid_self.heater.set_pwm

        # 2. Inject our interception logic
        self.pid_self.temperature_update = self._hijacked_temp_update
        logging.info(f"ApeControl: Hijacked {self.heater_name} temperature_update")

    def _hijacked_temp_update(self, read_time, temp, target_temp):
        """The entry point for every heater tick (usually 2Hz)"""
        try:
            # A. Temporarily redirect set_pwm to capture the PID intent
            self.pid_self.heater.set_pwm = self._capture_pwm
            
            # B. Run the original Klipper PID math
            self.orig_temp_update(read_time, temp, target_temp)
            
            # C. Hand off to the specific control architecture (PPControl, etc)
            # We restore the original set_pwm first so the child can use it
            self.pid_self.heater.set_pwm = self.orig_set_pwm
            
            disturbances = self._get_disturbances(read_time)
            final_pwm = self.compute_control(read_time, temp, target_temp, disturbances)
            
            # D. Apply final clamped power
            clamped_pwm = max(0.0, min(self.max_power, final_pwm))
            self.pid_self.heater.set_pwm(read_time, clamped_pwm)

        except Exception as e:
            # SAFETY FALLBACK: If our logic crashes, restore Klipper defaults
            logging.error(f"ApeControl Error in {self.heater_name}: {str(e)}")
            self._handle_fallback(read_time, temp, target_temp)

    def _capture_pwm(self, read_time, value):
        """Captures what the PID loop wanted to do"""
        self._captured_pid_pwm = value

    def _handle_fallback(self, read_time, temp, target_temp):
        """Emergency restoration of native Klipper control"""
        self.pid_self.temperature_update = self.orig_temp_update
        self.pid_self.heater.set_pwm = self.orig_set_pwm
        self.pid_self.temperature_update(read_time, temp, target_temp)
        logging.warning("ApeControl: Emergency fallback to native PID engaged.")

    def _get_disturbances(self, read_time):
        """Helper to gather system state for the controller"""
        # Example: Look up extruder velocity
        extruder = self.printer.lookup_object('extruder')
        e_vel = extruder.get_status(read_time).get('velocity', 0.0)
        
        return {
            'e_velocity': e_vel,
            'volumetric_flow': e_vel * 2.405, # Assumes 1.75mm
            'pid_pwm': self._captured_pid_pwm
        }

    @abstractmethod
    def compute_control(self, read_time, temp, target_temp, disturbances):
        """Sub-classes implement their math here"""
        pass