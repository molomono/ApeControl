import logging
from .base_controller import BaseController
from .state_look_ahead import StateLookahead

class PPControl(BaseController):
    def __init__(self, config):
        # Initialize the base (hijacks Klipper)
        super().__init__(config)


        # Register the ready handler to perform the hijack after Klipper is fully initialized
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

        # Load Architecture-specific parameters
        self.k_ss = config.getfloat('k_ss', 0.0)
        self.k_fan = config.getfloat('k_fan', 0.0)
        self.k_ev = config.getfloat('k_ev', 0.0)
        self.ev_smoothing = config.getfloat('ev_smoothing', 0.1)
        self.dt_first_layer = config.getfloat('dt_first_layer', 1.5)

        # Switching Logic Parameters
        self.t_overshoot_up = config.getfloat('t_overshoot_up', 0.0)
        self.coast_time_up = config.getfloat('coast_time_up', 0.0)
        self.t_overshoot_down = config.getfloat('t_overshoot_down', 0.0)
        self.coast_time_down = config.getfloat('coast_time_down', 0.0)

        # Regulation max error window
        self.t_delta_regulate = config.getfloat('t_delta_regulate', 5.0)
        self.min_regulation_duration = config.getfloat('min_duration', 5.0) # Minimum duration to stay in a state before transitioning (prevents chatter)

        # On off switch for feed-back control
        self.fb_enable = config.getboolean('fb_enable', True)

        ## State Machine State
        self.state = "off"
        self.last_state_change = 0.0
        self.e_velocity_filtered = 0.0
        
        ## State dispatch table
        self._states = {
            "off": self._state_off,
            "max_power": self._state_max_power,
            "coast_up": self._state_coast_up,
            "regulate": self._state_regulate,
            "min_power": self._state_min_power,
            "coast_down": self._state_coast_down
        }
        
        # Reference temperature (synced with PID)
        self.t_ref = 0.0

    def handle_ready(self):
        self.install_hijack()

        # Useful objects for proactive power compensation control logic
        self.part_fan = self.printer.lookup_object('fan')
        self.gcode_move = self.printer.lookup_object('gcode_move')
        self.gcode = self.printer.lookup_object('gcode')
        self.reactor = self.printer.get_reactor()

                
        self.gcode.register_command("CALIBRATE_APE", self.calibrate, 
                                    desc="Calibrate ApeControl parameters")

    def compute_control(self, pid_self, read_time, temp, target_temp):
        """The PP-Control implementation of Proactive Power Control
        
        Args:
            pid_self: The ControlPID instance from Klipper
            read_time: Current read time from Klipper
            temp: Current temperature reading
            target_temp: Target temperature (same as pid_self.t_ref after PID update)
        """
        # Check if target changed before updating
        target_changed = (target_temp != self.t_ref)
        
        # Sync local reference with PID target
        self.t_ref = target_temp
        
        # Call the original PID to update its internal state and capture the PWM
        # This is critical: it updates pid_self.prev_temp, prev_temp_deriv, etc.
        self.orig_temp_update(read_time, temp, target_temp)

        # Global Off Trigger
        if target_temp == 0:
            if self.state != "off":
                self._transition("off", read_time)
            return 0.0

        # Calculate Error and Duration
        error = target_temp - temp
        duration = read_time - self.last_state_change

        # Handle state transitions when target changes mid-coast (only if target actually changed)
        if self.state in ["coast_up", "coast_down"] and target_changed:
            self._transition("regulate", 0.0)  # Force transition to regulate, allowing min duration to be met for min/max state changes

        # State Dispatch: executes the logic for the current state and returns the power level
        if self.state == "regulate":
            power_output = self._state_regulate(error, duration, read_time, pid_self)
        else:
            power_output = self._states[self.state](error, duration, read_time)
        
        return power_output
    

    def ff_fb_control(self, pid_self, read_time):
        """Combine feed-forward and feedback control in regulate state
        
        Args:
            pid_self: The ControlPID instance to access captured PWM
            
        Returns:
            Combined PWM value (feed-forward + captured PID feedback)
        """
        u_fb_pid = self.captured_fb_pwm
        
        # Access Feed Forward inputs
        fan_speed = self.part_fan.get_status(read_time)['speed']
        e_velocity = self.printer.lookup_object('motion_report').get_status(read_time)['live_extruder_velocity'] # realtime, we can also use look-ahead in later versions
        z_position = self.gcode_move.get_status()['position'][2]
        if z_position < 0.3:
            fist_layer_compensation = self.dt_first_layer
        else:
            fist_layer_compensation = 0.0

        # Low-pass filter the error due to stuttery velocity readings. This should be solved by using look-ahead velocity for some known time constant beween power and temperature reading.
        self.e_velocity_filtered = min(0.0, (1 - self.ev_smoothing) * self.e_velocity_filtered + self.ev_smoothing * e_velocity)
        # Feed forward control logic
        u_ff = (self.t_ref - fist_layer_compensation) * self.k_ss + fan_speed * self.k_fan + self.e_velocity_filtered * self.k_ev

        
        logging.info("PP-Control Control Effort: PID_PWM: %.3f, FF_PWM: %.3f, FF_ev: %.3f" % (u_fb_pid, u_ff, self.e_velocity_filtered * self.k_ev))
        lookaheadtime = 1.0
        logging.info("PP-Control %.3f sec LookAhead: %.3f" % (lookaheadtime, self.state_lookahead.get_state_at('fan_speed', lookaheadtime, fan_speed)))

        if not self.fb_enable:
            return u_ff
        else:           
            return u_fb_pid + u_ff

    def _transition(self, next_state, read_time):
        """Transition to a new state and log the change"""
        if self.state != next_state:
            logging.info("[%.3f] PP-Control state transition: %s -> %s" % (read_time, self.state, next_state))
            self.state = next_state
            self.last_state_change = read_time

    # --- Logic for the individual states ---
    def _state_off(self, error, duration, read_time):
        """Off state: wait for non-zero target"""
        if error > 0:
            self._transition("max_power", read_time)
        return 0.0

    def _state_max_power(self, error, duration, read_time):
        """Max power state: heat until approaching target"""
        if error < self.t_overshoot_up:
            self._transition("coast_up", read_time)
        return 1.0

    def _state_coast_up(self, error, duration, read_time):
        """Coast up state: reduce power to prevent overshoot"""
        if duration >= self.coast_time_up:
            self._transition("regulate", read_time)
        return 0.0

    def _state_regulate(self, error, duration, read_time, pid_self=None):
        """Regulate state: maintain temperature with feedback control"""
        if abs(error) < self.t_delta_regulate or duration < self.min_regulation_duration: # Temp within regulation window or min duration not met
            return self.ff_fb_control(pid_self,read_time)
        elif error > self.t_delta_regulate:  # Temp too far below target
            self._transition("max_power", read_time)
            return 1.0
        elif error < -self.t_delta_regulate:  # Temp too far above target
            self._transition("min_power", read_time)
            return 0.0

    def _state_min_power(self, error, duration, read_time):
        """Min power state: reduce power when overshot"""
        if error > -self.t_overshoot_down:  # Error approaching zero from below
            self._transition("coast_down", read_time)
        return 0.0

    def _state_coast_down(self, error, duration, read_time):
        """Coast down state: coast to prevent undershoot"""
        if duration >= self.coast_time_down:
            self._transition("regulate", read_time)
        return 1.0
    
        
    # Add this to your ApeControl class in ape_control.py
    def calibrate(self, gcmd):
        target = gcmd.get_float('TARGET', 200.0)
        power = gcmd.get_float('POWER', 0.25) # 25% power for SS test
        heater = self.target_heater
        
        self.gcode.respond_info(f"PP-Control: Starting calibration for {target}C...")
        
        # --- PHASE 1: Transient Analysis (Slope & Overshoot) ---
        self.gcode.respond_info("Phase 1: Measuring Rise Slope and Overshoot...")
        heater.set_pwm(self.printer.get_reactor().monotonic(), 1.0) # Full Power
        
        start_time = self.printer.get_reactor().monotonic()
        start_temp = heater.get_status(start_time)['temperature']
        
        # Wait for target
        while heater.get_status(self.printer.get_reactor().monotonic())['temperature'] < target:
            self.printer.get_reactor().pause(self.printer.get_reactor().monotonic() + 0.5)
        
        hit_target_time = self.printer.get_reactor().monotonic()
        heater.set_pwm(hit_target_time, 0.0) # Power Off
        
        # Calculate Slope Up
        rise_slope = (target - start_temp) / (hit_target_time - start_time)
        self.gcode.respond_info(f"Slope Up: {rise_slope:.3f} C/s")

        # Capture Overshoot
        max_temp = target
        while True:
            self.printer.get_reactor().pause(self.printer.get_reactor().monotonic() + 0.5)
            current_temp = heater.get_status(self.printer.get_reactor().monotonic())['temperature']
            if current_temp > max_temp:
                max_temp = current_temp
            else:
                # Temperature started dropping
                break
                
        overshoot = max_temp - target
        self.gcode.respond_info(f"Overshoot captured: {overshoot:.2f} C")

        # --- PHASE 2: Cool Down & Steady State ---
        low_threshold = target * 0.8
        self.gcode.respond_info(f"Phase 2: Cooling to {low_threshold}C for SS test...")
        
        while heater.get_status(self.printer.get_reactor().monotonic())['temperature'] > low_threshold:
            self.printer.get_reactor().pause(self.printer.get_reactor().monotonic() + 1.0)

        # Steady State Test
        self.gcode.respond_info(f"Applying constant power {power*100}% for Steady-State analysis...")
        heater.set_pwm(self.printer.get_reactor().monotonic(), power)
        
        # Wait 2 minutes for thermal equilibrium
        self.printer.get_reactor().pause(self.printer.get_reactor().monotonic() + 120.0)
        
        ss_temp = heater.get_status(self.printer.get_reactor().monotonic())['temperature']
        k_ss = power / ss_temp
        
        self.gcode.respond_info("--- CALIBRATION COMPLETE ---")
        self.gcode.respond_info(f"Recommended K_SS: {k_ss:.6f}")
        self.gcode.respond_info(f"Recommended T_OVERSHOOT: {overshoot:.2f}")
        self.gcode.respond_info(f"Fall slope measurement is recommended via logs.")
        