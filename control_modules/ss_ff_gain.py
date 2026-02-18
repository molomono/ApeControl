import logging
from .base_controller import BaseController

class SSFFControl(BaseController):
    def __init__(self, config):
        # Initialize the base (hijacks Klipper)
        super().__init__(config)
        
        # Register the ready handler to perform the hijack after Klipper is fully initialized
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        # Load Architecture-specific parameters
        self.k_ss = config.getfloat('k_ss', 0.0)
        self.fb_enabled   = config.getboolean('fb_enabled', True)

    def handle_ready(self):
        self.install_hijack()

    def compute_control(self, pid_self, read_time, temp, target_temp):
        """Example of a simple Static State Feed-Forward gain with optional feedback from the original PID controller"""
        # If feedback is enabled, we call the original PID to capture its PWM output.
        if self.fb_enabled:
            self.orig_temp_update(read_time, temp, target_temp)
        
        # Get the captured PID PWM from the original controller 0 if feedback disabled.
        u_fb_pid = self.captured_fb_pwm
        # Compute the steady-state feed-forward term based on the target temperature
        u_ff_ss = target_temp * self.k_ss
        
        logging.info("SS-FF-Control: PID_PWM: %s, FFC_PWM: %s" % (u_fb_pid, u_ff_ss))
        # We add the original PID logic (Feedback) to our Feed-Forward terms
        return u_fb_pid + u_ff_ss