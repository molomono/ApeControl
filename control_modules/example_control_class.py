import logging
from .base_controller import BaseController

class ExampleControl(BaseController):
    """
    Template/Example control class for implementing custom temperature controllers.
    
    This class serves as a blank template showing the structure needed to create
    new control algorithms that integrate with Klipper's PID system via monkey patching.
    
    To create a new controller:
    1. Inherit from BaseController
    2. Implement __init__ with your config parameters
    3. Register the 'klippy:ready' event handler --> This performs the monkey patch.
    4. Implement compute_control() with your algorithm
    5. Optionally implement state machines or other logic
    
    The base class handles:
    - Monkey patching the original ControlPID.temperature_update()
    - Capturing the original PID's PWM output
    - Providing access to Klipper's printer objects
    """
    
    def __init__(self, config):
        """
        Initialize your custom controller.
        
        Args:
            config: Klipper config object for this section
            
        This is where you:
        - Call super().__init__(config) to set up base functionality
        - Load your custom configuration parameters using config.getfloat(), etc.
        - Register event handlers (especially 'klippy:ready')
        - Initialize any internal state variables
        """
        # Always call super().__init__ first
        super().__init__(config)
        
        # Register ready handler - CRITICAL for proper initialization timing
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        # TODO: Load your configuration parameters here
        # self.my_param = config.getfloat('my_param', default_value)
        
        # TODO: Initialize internal state variables here
        # self.state_variable = 0.0

    def handle_ready(self):
        """
        Called when Klipper is fully initialized and ready.
        
        This is where you perform the monkey patch hijack.
        NEVER call install_hijack() before this point - Klipper objects may not exist yet.
        """
        self.install_hijack()

    def compute_control(self, pid_self, read_time, temp, target_temp):
        """
        Your main control algorithm implementation.
        
        This method is called instead of the original ControlPID.temperature_update().
        It receives the same parameters and must return a PWM value between 0.0 and 1.0.
        
        Args:
            pid_self: The original ControlPID instance (access via pid_self.heater.set_pwm())
            read_time: Current Klipper read time (float)
            temp: Current temperature reading (float)
            target_temp: Target temperature setpoint (float)
            
        Returns:
            PWM output value (0.0 to 1.0)
            
        Key points:
        - Call self.orig_temp_update(read_time, temp, target_temp) FIRST to update PID state
        - Access captured original PID PWM via self.captured_fb_pwm
        - Use self.t_ref for target temperature (synced automatically)
        - Base class handles clamping to [0,1]
        """
        # CRITICAL: Always call this first to maintain PID internal state
        # This updates pid_self.prev_temp, prev_temp_deriv, etc.
        self.orig_temp_update(read_time, temp, target_temp)
        
        # TODO: Implement your control algorithm here
        
        # Example structure:
        # if target_temp == 0:
        #     return 0.0
        # 
        # error = target_temp - temp
        # output = your_algorithm(error, self.captured_fb_pwm, etc.)
        # 
        # return output
        
        # Placeholder - replace with your implementation
        return 0.0