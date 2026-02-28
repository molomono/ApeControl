# ApeControl-Klipper modified PID class
#
# Original Author and code: Kevin O'Connor <kevin@koconnor.net>
# https://github.com/Klipper3d/klipper/blob/master/klippy/extras/heaters.py
#
# Modifications for ApeControl compatiblity: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from .base_controller import BaseController

PID_PARAM_BASE = 255.
AMBIENT_TEMP = 25.

PID_SETTLE_DELTA = 1.
PID_SETTLE_SLOPE = .1

class PIDControl(BaseController):
    def __init__(self, config):
        super().__init__(config)
        # Hardcoded Params
        self.algo_name = "PID-Control"
        
        # Config Params
        self.Kp = config.getfloat('pid_Kp', 0.0) / PID_PARAM_BASE
        self.Ki = config.getfloat('pid_Ki', 0.0) / PID_PARAM_BASE
        self.Kd = config.getfloat('pid_Kd', 0.0) / PID_PARAM_BASE
        self.min_deriv_time = config.getfloat('pid_deriv_time', 2., above=0.)
        
        # Initial vars
        self.temp_integ_max = 0.
        if self.Ki:
            self.temp_integ_max = self.max_power / self.Ki
        self.prev_temp = AMBIENT_TEMP
        self.prev_temp_time = 0.
        self.prev_temp_deriv = 0.
        self.prev_temp_integ = 0.
        self.co = 0.

    def temperature_update(self, read_time, temp, target_temp):
        time_diff = read_time - self.prev_temp_time
        temp_diff = temp - self.prev_temp
        if time_diff >= self.min_deriv_time:
            temp_deriv = temp_diff / time_diff
        else:
            temp_deriv = (self.prev_temp_deriv * (self.min_deriv_time - time_diff) + temp_diff) / self.min_deriv_time
        temp_err = target_temp - temp
        temp_integ = self.prev_temp_integ + temp_err * time_diff
        temp_integ = max(0., min(self.temp_integ_max, temp_integ))
        self.co = self.Kp * temp_err + self.Ki * temp_integ - self.Kd * temp_deriv
        bounded_co = max(0., min(self.max_power, self.co))
        self.set_pwm(read_time, bounded_co)
        self.prev_temp = temp
        self.prev_temp_time = read_time
        self.prev_temp_deriv = temp_deriv
        if self.co == bounded_co:
            self.prev_temp_integ = temp_integ

    def check_busy(self, eventtime, smoothed_temp, target_temp):
        temp_diff = target_temp - smoothed_temp
        return (abs(temp_diff) > PID_SETTLE_DELTA
                or abs(self.prev_temp_deriv) > PID_SETTLE_SLOPE)
