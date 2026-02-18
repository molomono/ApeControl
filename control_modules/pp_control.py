import logging
from .base_controller import BaseController

class PPControl(BaseController):
    def __init__(self, config):
        # Initialize the base (hijacks Klipper)
        super().__init__(config)
        
        # Register the ready handler to perform the hijack after Klipper is fully initialized
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        # Load Architecture-specific parameters
        self.k_ss = config.getfloat('k_ss', 0.0)
        self.t_overshoot = config.getfloat('t_overshoot', 0.0)
        self.k_flow = config.getfloat('k_flow', 0.0)

    def handle_ready(self):
        self.install_hijack()

    def compute_control(self, pid_self, read_time, temp, target_temp):
        """The PP-Control implementation of Proactive Power Control"""
        #error = target_temp - temp
        self.orig_temp_update(read_time, temp, target_temp) # Run the original PID to get the PWM value for feed-forward    
        u_fb_pid = self.get_pid_pwm()
        
        # 1. Nonlinear State Selection
        # Slew State (Full Power)
        #if error > (self.t_overshoot + 1.0):
        #    return 1.0
            
        # Coast State (Zero Power to bleed momentum)
        #if 0 < error <= self.t_overshoot:
        #    return 0.0
            
        # 2. Regulate State (FF + FB)
        u_ff_ss = target_temp * self.k_ss
        
        logging.info("PP-Control: PID_PWM: %s, FFC_PWM: %s" % (u_fb_pid, u_ff_ss))
        # We add the original PID logic (Feedback) to our Feed-Forward terms
        return u_fb_pid + u_ff_ss