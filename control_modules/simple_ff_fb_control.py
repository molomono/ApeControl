import logging
from .base_controller import BaseController

class SimpleFFFBControl(BaseController):
    def __init__(self, config):
        super().__init__(config)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

        # Feed-forward control parameters
        self.k_ss = config.getfloat('k_ss', 0.0)    # Feed-forward steady state gain
        self.tau = config.getfloat('tau', 20.0)      # Time Delta heater (seconds in T until 63% of target temp is reached)
        self.t_filter = config.getfloat('t_filter', 0.025)    # filter time constant
        
        self.fb_enable = config.getboolean('fb_enable', True)   # Feedback gain
        
        # Internal state for derivative calculation
        self.target_deriv = 0.0
        self.prev_filtered_target_deriv = 0.0
        self.prev_target = 0.0
        
    def handle_ready(self):
        self.install_hijack()
        
    def compute_control(self, pid_self, read_time, temp, target_temp):
        if target_temp == 0:
            return 0.0
        
        self.orig_temp_update(read_time, temp, target_temp)
        
        target_diff = target_temp - self.prev_target
        # Pulling necissary variables into the function scope for readability
        time_diff = read_time - pid_self.prev_temp_time
        min_deriv_time = pid_self.min_deriv_time

        if time_diff >= min_deriv_time:
            self.target_deriv = target_diff / time_diff
            self.alpha = self.t_filter / (self.t_filter + time_diff)
        else:
            self.target_deriv = (target_diff * (self.min_deriv_time-time_diff)
                          + target_diff) / self.min_deriv_time
            self.alpha = self.t_filter / (self.t_filter + min_deriv_time)

        target_deriv_filtered = self.alpha * self.prev_filtered_target_deriv + (1 - self.alpha) * self.target_deriv
            
        # Actual control law u_ff = k_ss*r + k_dy*dr/dt, k_dy = tau*k_ss
        u_ff = self.k_ss * (target_temp + self.tau * target_deriv_filtered)

        self.prev_filtered_target_deriv = target_deriv_filtered
        self.prev_target = target_temp
        
        # If feedback is enabled, we add the original PID output to our feed-forward term.
        if self.fb_enable:
            return u_ff + self.captured_fb_pwm
        else:
            return u_ff
        
        