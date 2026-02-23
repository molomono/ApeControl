# ApeControl-Klipper AutoTuning script for PP-control
#
# Original author and code: Kevin O'Connor <kevin@koconnor.net>
# Derivative author and code: Molomono 
# Modified but based on the original PID autocalibration code.
# This file may be distributed under the terms of the GNU GPLv3 license.
import math, logging
import logging


PARAM_BASE = 255.
TEMP_AMBIENT = 20.

class PPCalibrate:
    def __init__(self, config):
        self.printer = config.get_printer()
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('PP_CALIBRATE', self.cmd_PP_CALIBRATE,
                               desc=self.cmd_PP_CALIBRATE_help)
    cmd_PP_CALIBRATE_help = "Run PP calibration test"
    
    def cmd_PP_CALIBRATE(self, gcmd):
        logging.info("Autotune: APECONTROL calibration test")
        # Target temperature and command arguments
        heater_name = gcmd.get('HEATER')
        target = gcmd.get_float('TARGET')
        write_file = gcmd.get_int('WRITE_FILE', 0)
        # Load objects
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(heater_name)
        except self.printer.config_error as e:
            raise gcmd.error(str(e))
        self.printer.lookup_object('toolhead').get_last_move_time()

        # Create a new instance of the AutoTune class.
        calibrate = ControlAutoTune(heater, target)
        old_control = heater.set_control(calibrate)
        logging.info("ApeControl: Heater object '%s' controller exchanged with %s algorithm", heater_name, calibrate.algo_name)
        try:
            pheaters.set_temperature(heater, target, True)
        except self.printer.command_error as e:
            heater.set_control(old_control)
            raise
        heater.set_control(old_control) # Restore actual controller after calibration test
        logging.info("ApeControl: Heater object '%s' controller has been restored to %s", heater_name, old_control.algo_name)
        if write_file:
            calibrate.write_file('/tmp/heattest.txt')
        if calibrate.check_busy(0., 0., 0.):
            raise gcmd.error("%s interrupted"%(calibrate.algo_name))
        
        ########## Actual calibraiton logic, data has been collected in ControlAutoTune lists.
        # Log and report results
        Kss,Ku,Tu,tau,L,omega_u = calibrate.calc_final_fowdt()
        #Kp, Ki, Kd = calibrate.calc_final_pid()
        autotune_report = "%s: Kss=%.3f,Ku=%.3f,Tu=%.3f,omega_u=%.3f,tau=%.3f,L=%.3f" % (calibrate.algo_name, Kss,Ku,Tu,omega_u,tau,L)
        logging.info(autotune_report)
        
        gcmd.respond_info(
            autotune_report + "\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with these parameters and restart the printer.")
        
        # Store results for SAVE_CONFIG
        cfgname = heater.get_name()
        configfile = self.printer.lookup_object('configfile')
        configfile.set(cfgname, 'control', 'pp_control')
        #configfile.set(cfgname, 'Ku', "%.3f" % (Ku,))
        #configfile.set(cfgname, 'Tu', "%.3f" % (Tu,))
        configfile.set(cfgname, 'K_ss', "%.3f" % (Kss,))
        #configfile.set(cfgname, 'tau', "%.3f" % (Kss,))
        #configfile.set(cfgname, 'L', "%.3f" % (Kss,))


TUNE_PID_DELTA = 5.0

class ControlAutoTune:
    def __init__(self, heater, target):
        self.algo_name = "PP-AutoTune"
        self.heater = heater
        self.target = target # used for Kss computation later
        self.heater_max_power = heater.get_max_power()
        self.calibrate_temp = target
        # Heating control
        self.heating = False
        self.peak = 0.
        self.peak_time = 0.
        # Peak recording
        self.peaks = [] # (temp, time)
        # Sample recording
        self.last_pwm = 0.
        self.pwm_samples = []
        self.temp_samples = []
    # Heater control 
    def set_pwm(self, read_time, value):
        if value != self.last_pwm:
            self.pwm_samples.append(
                (read_time + self.heater.get_pwm_delay(), value))
            self.last_pwm = value
        self.heater.set_pwm(read_time, value)
    def temperature_update(self, read_time, temp, target_temp):
        self.temp_samples.append((read_time, temp))
        # Check if the temperature has crossed the target and
        # enable/disable the heater if so.
        if self.heating and temp >= target_temp:
            self.heating = False
            self.check_peaks()
            self.heater.alter_target(self.calibrate_temp - TUNE_PID_DELTA)
        elif not self.heating and temp <= target_temp:
            self.heating = True
            self.check_peaks()
            self.heater.alter_target(self.calibrate_temp)
        # Check if this temperature is a peak and record it if so
        if self.heating:
            self.set_pwm(read_time, self.heater_max_power)
            if temp < self.peak:
                self.peak = temp
                self.peak_time = read_time
        else:
            self.set_pwm(read_time, 0.)
            if temp > self.peak:
                self.peak = temp
                self.peak_time = read_time

        self.compute_steadystate()

    def check_busy(self, eventtime, smoothed_temp, target_temp):
        if self.heating or len(self.peaks) < 12:
            return True
        return False
    
    # Analysis
    def compute_steadystate(self):
        pass# for now
    
    def check_peaks(self):
        self.peaks.append((self.peak, self.peak_time))
        if self.heating:
            self.peak = 9999999.
        else:
            self.peak = -9999999.
        if len(self.peaks) < 4:
            return

    def calc_fowdt(self, pos):
        temp_diff = self.peaks[pos][0] - self.peaks[pos-1][0]
        time_diff = self.peaks[pos][1] - self.peaks[pos-2][1]

        # Does this cycle start at a temperature highpoint or lowpoint
        if temp_diff >= 0:
            start_on_peak = True
        else:
            start_on_peak = False

        # Use Astrom-Hagglund method to estimate Ku and Tu
        amplitude = .5 * abs(temp_diff)
        Ku = 4. * self.heater_max_power / (math.pi * amplitude)
        Tu = time_diff
       
        # Estimate Kss from on-off dutycycle to maintain averaged target temp
        #if start_on_peak:
        #    pulse_width = 1 - self.peaks[pos][1] - self.peaks[pos-1][1]
        #else:
        pulse_width = self.peaks[pos][1] - self.peaks[pos-1][1]

        #TODO: Change the above logic to use:
        #self.pwm_samples = (event_time, value)
        # Load these values self.pwm_samples[pos]
        logging.info("%s: pwm_samples: %s", self.algo_name, self.pwm_samples)
        logging.info("%s: peaks: %s", self.algo_name, self.peaks)
        # Compute the ratio of on to off time. This is our Kss - sensitivty
        first_peak_temp = self.peaks[2][0]
        first_peak_time = self.peaks[2][1]
        pulse_width_first_pulse =  self.pwm_samples[2][0] - self.pwm_samples[1][0]
        pulse_state_first_pulse =  self.pwm_samples[1][1]

        second_peak_temp = self.peaks[3][0]
        second_peak_time = self.peaks[3][1]
        pulse_width_second_pulse =  self.pwm_samples[3][0] - self.pwm_samples[2][0]
        pulse_state_second_pulse =  self.pwm_samples[2][1]

        time_to_peak_rising_edge = first_peak_time-self.pwm_samples[1][0]
        time_to_peak_falling_edge = second_peak_time-self.pwm_samples[2][0]
        logging.info("%s: t_overshoot_up %.3f, coast_time_up %.3f, t_overshoot_down %.3f, coast_time_down %.3f", self.algo_name, first_peak_temp-self.target, time_to_peak_rising_edge, self.target-TUNE_PID_DELTA - second_peak_temp, time_to_peak_falling_edge)
        logging.info("%s: actuator duty cycle: %.3f", pulse_width_second_pulse/(pulse_state_first_pulse + pulse_state_second_pulse))
        #TODO: Look at the time between switching the power off during a rising edge
        # compute t_overshoot_up --> peak temperature above our setpoint.
        # compute t_overshoot_down --> peak temperature below our setpoint-TUNE_PID_DELTA

        duty_cycle = pulse_width / Tu # pulse width divided by the period
        Kss_est =  duty_cycle / self.target # estimated steady state power ratio of max power
        Kss = Kss_est
        # Compute FOWDT model parameters
        omega_u  = (2*math.pi) / Tu # critical frequency
        K = (self.target - TEMP_AMBIENT) / max(duty_cycle, 0.001)
        gain_product = K * Ku

        if gain_product <= 1.0:
            raise logging.error("%s: AutoTune failed measured gain-product is too low.", self.algo_name)
        tau = math.sqrt(gain_product**2 - 1) / omega_u # Time constant
        L = (math.pi - math.atan(omega_u*tau)) / omega_u # Dead time
        
        return Kss,Ku,Tu,tau,L,omega_u
    
    def calc_final_fowdt(self):
        cycle_times = [(self.peaks[pos][1] - self.peaks[pos-2][1], pos)
                       for pos in range(4, len(self.peaks))]
        midpoint_pos = sorted(cycle_times)[len(cycle_times)//2][1]
        return self.calc_fowdt(midpoint_pos)

    
    # Offline analysis helper
    def write_file(self, filename):
        pwm = ["pwm: %.3f %.3f" % (time, value)
               for time, value in self.pwm_samples]
        out = ["%.3f %.3f" % (time, temp) for time, temp in self.temp_samples]
        f = open(filename, "w")
        f.write('\n'.join(pwm + out))
        f.close()

def load_config(config):
    return PPCalibrate(config)