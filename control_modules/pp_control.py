# ApeControl-Klipper PP Control algorithm code
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math
import logging
from .base_controller import BaseController

SETTLE_DELTA = 1.
SETTLE_SLOPE = .1
AMBIENT_TEMP = 25.

class PPControl(BaseController):
    def __init__(self, config):
        # Initialize the base (hijacks Klipper)
        super().__init__(config)
        # Hardcoded Params
        self.algo_name = "PP-Control"

        # Load Architecture-specific parameters
        self.k_ss = config.getfloat('k_ss', 0.0)
        self.k_fan = config.getfloat('k_fan', 0.0)
        self.k_ev = config.getfloat('k_ev', 0.0)
        self.ev_smoothing = config.getfloat('ev_smoothing', 0.075)
        self.dt_first_layer = config.getfloat('dt_first_layer', 1.5)

        # Switching Logic Parameters
        self.t_overshoot_up = config.getfloat('t_overshoot_up', 0.0)
        self.coast_time_up = config.getfloat('coast_time_up', 0.0)
        self.t_overshoot_down = config.getfloat('t_overshoot_down', 0.0)
        self.coast_time_down = config.getfloat('coast_time_down', 0.0)

        # Regulation max error window
        self.t_delta_regulate = config.getfloat('t_delta_regulate', 10.0)
        self.min_regulation_duration = config.getfloat('min_duration', 10.0) # Minimum duration to stay in a state before transitioning (prevents chatter)

        # On off switch for feed-back control
        self.fb_enable = config.getboolean('fb_enable', True)

        # Min derivative time, for computing temp velocity
        self.min_deriv_time = config.getfloat('deriv_time', 2., above=0.)

        ## State Machine State
        self.state = "off"
        self.last_state_change = 0.0
        self.e_velocity_filtered = 0.0
        self.prev_temp_deriv = 0.
        self.prev_temp = AMBIENT_TEMP
        self.prev_temp_time = 0.
        
        ## State dispatch table
        self._states = {
            "off": self._state_off,
            "max_power": self._state_max_power,
            "coast_up": self._state_coast_up,
            "regulate": self._state_regulate,
            "min_power": self._state_min_power,
            "coast_down": self._state_coast_down
        }

        if self.fb_enable:
            self.fb_pwm = 0.0
            from .pid_control import PIDControl
            self.feedback_controller = PIDControl(config)
            self.feedback_controller.set_pwm = lambda read_time, value: setattr(self, 'fb_pwm', value)   

    def temperature_update(self, read_time, temp, target_temp):
        """The PP-Control implementation of Proactive Power Control
        
        Args:
            read_time: Current read time from Klipper
            temp: Current temperature reading
            target_temp: Target temperature (same as self.target_temp after PID update)
        """
        #
        if self.fb_enable: # pass inputs to the feedback controller. TODO: move to the ff_fb loop
            self.feedback_controller.temperature_update(read_time, temp, target_temp)

        # Check if target changed before updating
        target_changed = (target_temp != self.target_temp)
        
        # Sync local reference with PID target
        self.target_temp = target_temp
        time_diff = read_time - self.prev_temp_time
        temp_diff = temp - self.prev_temp
        if time_diff >= self.min_deriv_time:
            temp_deriv = temp_diff / time_diff
        else:
            temp_deriv = (self.prev_temp_deriv * (self.min_deriv_time - time_diff) + temp_diff) / self.min_deriv_time

        # Call the original PID to update its internal state and capture the PWM
        # This is critical: it updates pid_self.prev_temp, prev_temp_deriv, etc.
        #self.orig_temp_update(read_time, temp, target_temp)

        # Global Off Trigger
        if target_temp <= 0:
            self.set_pwm(read_time, 0.0)  # Always set hardware to off
            if self.state != "off":
                self._transition("off", read_time)
        else:
            # Calculate Error and Duration
            error = target_temp - temp
            duration = read_time - self.last_state_change

            # Handle state transitions when target changes mid-coast (only if target actually changed)
            if self.state in ["coast_up", "coast_down"] and target_changed:
                self._transition("regulate", 0.0)  # Force transition to regulate, allowing min duration to be met for min/max state changes

            # State Dispatch: executes the logic for the current state and returns the power level
            if self.state == "regulate":
                co = self._state_regulate(error, duration, read_time)
            else:
                co = self._states[self.state](error, duration, read_time)
            
            bounded_co = max(0., min(self.heater_max_power, co))
            # Set PWM output (assumes heater object is accessible via self.printer)
            self.set_pwm(read_time, bounded_co)

            # Update previous temperature/time for next derivative calculation
            self.prev_temp = temp
            self.prev_temp_time = read_time
            self.prev_temp_deriv = temp_deriv
        
    def ff_fb_control(self, read_time):
        """Combine feed-forward and feedback control in regulate state
        
        Args:
            read_time: Event time at which to read sensors and commands.
            
        Returns:
            Combined PWM value (feed-forward + captured PID feedback)
        """
        # this is where the fb function should actually be called
        if self.fb_enable:
            u_fb_pid = self.fb_pwm
            u_fb_bidirection = max(-self.heater_max_power, min(self.heater_max_power, self.feedback_controller.co))
        else:
            u_fb_pid = 0.0k
            u_fb_bidirection = 0.0

        # Access Feed Forward inputs
        fan_speed = self.part_fan.get_status(read_time)['speed']
        e_velocity = self.printer.lookup_object('motion_report').get_status(read_time)['live_extruder_velocity'] # realtime, we can also use look-ahead in later versions
        z_position = self.gcode_move.get_status()['position'][2]
        if z_position < 0.3:
            fist_layer_compensation = self.dt_first_layer
        else:
            fist_layer_compensation = 0.0

        # Low-pass filter the error due to stuttery velocity readings. This should be solved by using look-ahead velocity for some known time constant beween power and temperature reading.
        self.e_velocity_filtered = max(0.0, (1 - self.ev_smoothing) * self.e_velocity_filtered + self.ev_smoothing * e_velocity)
        # Feed forward control logic
        u_ff = (self.target_temp - fist_layer_compensation) * self.k_ss + fan_speed * self.k_fan + self.e_velocity_filtered * self.k_ev

        
        logging.info("%s: Control Effort: FB_PWM: %.3f, FF_PWM: %.3f, FF_ev: %.3f" % (self.algo_name, u_fb_bidirection, u_ff, self.e_velocity_filtered * self.k_ev))
        
        if not self.fb_enable:
            return u_ff
        else:           
            return u_fb_bidirection + u_ff # u_fb_pid + u_ff was old implemenation

    def _transition(self, next_state, read_time):
        """Transition to a new state and log the change"""
        if self.state != next_state:
            logging.info("[%.3f] %s: state transition: %s -> %s" % (read_time, self.algo_name, self.state, next_state))
            if (next_state is "off" or next_state is "coast_up" or next_state is "coast_down"): # reset integrator to avoid carying prexisting errors into new control states.
                self.feedback_controller.prev_temp_integ = 0.
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
        # Immediate jump to regulate if temp slope is 0 or less
        if self.prev_temp_deriv <= 0:
            self._transition("regulate", read_time)
        elif duration >= self.coast_time_up:
            self._transition("regulate", read_time)
        return 0.0

    def _state_regulate(self, error, duration, read_time):
        """Regulate state: maintain temperature with feedback control"""
        if abs(error) < self.t_delta_regulate or duration < self.min_regulation_duration: # Temp within regulation window or min duration not met
            return self.ff_fb_control(read_time)
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
        # Immediate jump to regulate if temp slope is 0 or more
        if self.prev_temp_deriv >= 0:
            self._transition("regulate", read_time)
        elif duration >= self.coast_time_down:
            self._transition("regulate", read_time)
        return 1.0
    
    def check_busy(self, eventtime, smoothed_temp, target_temp):
        temp_diff = target_temp - smoothed_temp
        return (abs(temp_diff) > SETTLE_DELTA
                or abs(self.prev_temp_deriv) > SETTLE_SLOPE)
    