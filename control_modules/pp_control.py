from base_controller import BaseController


class PPControl(BaseController):
    def __init__(self, config, pid_self):
        # Initialize the base (hijacks Klipper)
        super().__init__(config, pid_self)
        
        # Load Architecture-specific parameters
        self.k_ss = config.getfloat('k_ss', 0.0)
        self.t_overshoot = config.getfloat('t_overshoot', 0.0)
        self.k_flow = config.getfloat('k_flow', 0.0)

    def compute_control(self, read_time, temp, target_temp, disturbances):
        """The PP-Control implementation of Proactive Power Control"""
        error = target_temp - temp
        pid_intent = disturbances['pid_pwm']
        
        # 1. Nonlinear State Selection
        # Slew State (Full Power)
        if error > (self.t_overshoot + 1.0):
            return 1.0
            
        # Coast State (Zero Power to bleed momentum)
        if 0 < error <= self.t_overshoot:
            return 0.0
            
        # 2. Regulate State (FF + FB)
        u_ff_ss = target_temp * self.k_ss
        u_ff_flow = disturbances['volumetric_flow'] * self.k_flow
        
        # We add the original PID logic (Feedback) to our Feed-Forward terms
        return pid_intent + u_ff_ss + u_ff_flow