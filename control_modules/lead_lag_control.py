import logging
from .base_controller import BaseController

class LeadLagControl(BaseController):
    """
    Feed-forward Lead-Lag Compensator for temperature control.
    
    This controller implements a lead-lag compensator that provides phase lead
    for improved stability and lag for noise reduction. It uses feed-forward
    control based on the target temperature with lead-lag compensation.
    
    Configuration parameters:
    - k_lead: Lead gain coefficient
    - k_lag: Lag gain coefficient  
    - tau_lead: Lead time constant
    - tau_lag: Lag time constant
    - alpha: Lead-lag ratio (tau_lead/tau_lag)
    """
    
    def __init__(self, config):
        # Initialize the base (hijacks Klipper)
        super().__init__(config)
        
        # Load compensator parameters
        self.k_lead = config.getfloat('k_lead', 1.0)
        self.k_lag = config.getfloat('k_lag', 0.1)
        self.tau_lead = config.getfloat('tau_lead', 10.0)
        self.tau_lag = config.getfloat('tau_lag', 100.0)
        self.alpha = config.getfloat('alpha', self.tau_lead / self.tau_lag)
        
        # Internal state for lag compensation
        self.prev_output = 0.0
        self.prev_error = 0.0
        self.integral_term = 0.0
        
        # Reference temperature
        self.t_ref = 0.0

        # Register the ready handler to perform the hijack after Klipper is fully initialized
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def handle_ready(self):
        self.install_hijack()

    def compute_control(self, pid_self, read_time, temp, target_temp):
        """
        Lead-Lag compensator implementation.
        
        The lead-lag compensator provides:
        - Lead component: Anticipates changes for faster response
        - Lag component: Filters noise and prevents oscillations
        
        Args:
            pid_self: The ControlPID instance from Klipper
            read_time: Current read time from Klipper
            temp: Current temperature reading
            target_temp: Target temperature
            
        Returns:
            Compensated PWM output (0.0 to 1.0)
        """
        # Update reference
        self.t_ref = target_temp
        
        # Call original PID to maintain state (critical for Klipper integration)
        self.orig_temp_update(read_time, temp, target_temp)
        
        # Off state
        if target_temp == 0:
            self.prev_output = 0.0
            self.prev_error = 0.0
            self.integral_term = 0.0
            return 0.0
        
        # Calculate error
        error = target_temp - temp
        
        # Lead component (proportional + derivative-like)
        lead_term = self.k_lead * (error - self.alpha * self.prev_error)
        
        # Lag component (integral-like filtering)
        dt = read_time - getattr(self, 'last_time', read_time)
        self.last_time = read_time
        
        if dt > 0:
            self.integral_term += self.k_lag * error * dt / self.tau_lag
            # Apply lag filtering
            lag_term = self.integral_term * (1 - dt / self.tau_lag)
        
        # Combine lead and lag
        output = lead_term + lag_term
        
        # Add feed-forward based on target
        ff_term = self.t_ref * 0.01  # Simple feed-forward scaling
        
        total_output = output + ff_term
        
        # Store state for next iteration
        self.prev_error = error
        self.prev_output = total_output
        
        
        logging.info("Lead-Lag: error=%.2f, lead=%.3f, lag=%.3f, ff=%.3f, output=%.3f" % 
                    (error, lead_term, lag_term, ff_term, total_output))
        
        return total_output