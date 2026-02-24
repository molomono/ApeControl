# ApeControl-Klipper AutoTuning script for PP-control
#
# Original author and code: Kevin O'Connor <kevin@koconnor.net>
# Derivative author and code: Molomono 
# Modified but based on the original PID autocalibration code.
# This file may be distributed under the terms of the GNU GPLv3 license.
import math, logging
import logging
from types import SimpleNamespace

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
        Kss,Ku,Tu,tau,L,omega_u, t_overshoot_up, t_overshoot_down, coast_time_up, coast_time_down, pid_kp, pid_ki, pid_kd = calibrate.calc_final_fowdt()
        #Kp, Ki, Kd = calibrate.calc_final_pid()
        autotune_report = "%s: Kss=%.6f,Ku=%.3f,Tu=%.3f,omega_u=%.3f,tau=%.3f,L=%.3f" % (calibrate.algo_name, Kss,Ku,Tu,omega_u,tau,L)
        logging.info(autotune_report)
        
        ######## Test for passing config variables as a dict, --> To implement DRY of configfile update/saving function
        logging.info("%s: ConfigVarsDict = %s", calibrate.algo_name, vars(calibrate.configvars))

        autotune_report_pid = "%s: AMIGO-PID values Kp=%.3f, Ki=%.3f, Kd=%.3f" % (calibrate.algo_name, pid_kp, pid_ki, pid_kd)
        logging.info(autotune_report_pid)
        gcmd.respond_info(
            autotune_report + "\n" + autotune_report_pid + "\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with these parameters and restart the printer.")
        
        # Store results for SAVE_CONFIG
        cfgname = "ape_control " + heater.get_name() # [ape_control heater_name]
        configfile = self.printer.lookup_object('configfile')
        configfile.set(cfgname, 'control', 'pp_control')
        configfile.set(cfgname, 'K_ss', "%.6f" % (Kss,))
        configfile.set(cfgname, 't_overshoot_up', "%.3f" % (t_overshoot_up,))
        configfile.set(cfgname, 'coast_time_up', "%.3f" % (coast_time_up,))
        configfile.set(cfgname, 't_overshoot_down', "%.3f" % (t_overshoot_down,))
        configfile.set(cfgname, 'coast_time_down', "%.3f" % (coast_time_down  - L/3,))
        configfile.set(cfgname, 'min_duration', "%.3f" % (L,) )
        
        configfile.set(cfgname, 'fb_enable', "True")
        configfile.set(cfgname, 'pid_kp', "%.3f" % (pid_kp,) )
        configfile.set(cfgname, 'pid_ki', "%.3f" % (pid_ki,) )
        configfile.set(cfgname, 'pid_kd', "%.3f" % (pid_kd,) )

        ######## SteadyState Calibration sequence
        ### WIP ....
        #self.run_autotune(calibrate,configvars=None)
        #calibrate = SSAutoTune(heater, target, Kss)
        #old_control = heater.set_control(calibrate)
        #logging.info("ApeControl: Heater object '%s' controller exchanged with %s algorithm", heater_name, calibrate.algo_name)
        #try:
        #    pheaters.set_temperature(heater, target)
        #except self.printer.command_error as e:
        #    heater.set_control(old_control)
        #    raise
        #heater.set_control(old_control) # Restore actual controller after calibration test
        #logging.info("ApeControl: Heater object '%s' controller has been restored to %s", heater_name, old_control.algo_name)
        #if write_file:
        #    calibrate.write_file('/tmp/heattest.txt')
        #if calibrate.check_busy(0., 0., 0.):
        #    raise gcmd.error("%s interrupted"%(calibrate.algo_name))
        
        #self.save_results(cfgname, vars(calibrate.configvars))
        # Can make the following a function
        # Args: AutoTuneClass, heater, target
        # TODO: return dict with tuned vars and values. {'Kss': 0.001, "t_overshoot_up": ..., etc} 
        # Add self.store_results(cfgname, tuned_var_dict)
        # load configfile and save dict contents.

    def save_results(self, cfgname, tuned_var_dict):
        # Automatically save all variables in passed dictionary
        logging.info("ApeControl: Saving vars to %s, Vars: %s" %(cfgname, tuned_var_dict))
        configfile = self.printer.lookup_object('configfile')
        for key, value in tuned_var_dict.items():
            configfile.set(cfgname, key, "%.5f" % (value,) )
        

TUNE_PID_DELTA = 5.0

class ControlAutoTune:
    def __init__(self, heater, target):
        self.algo_name = "PP-AutoTune"
        self.configvars = SimpleNamespace()
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

    def check_busy(self, eventtime, smoothed_temp, target_temp):
        if self.heating or len(self.peaks) < 12:
            return True
        return False
    
   
    def check_peaks(self):
        self.peaks.append((self.peak, self.peak_time))
        if self.heating:
            self.peak = 9999999.
        else:
            self.peak = -9999999.
        if len(self.peaks) < 4:
            return
    # Analysis functions
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
        first_off_switch = self.pwm_samples[1][0]
        last_off_switch  = self.pwm_samples[-1][0]
        pulse_width_first_pulse =  self.pwm_samples[2][0] - self.pwm_samples[1][0]
        pulse_state_first_pulse =  self.pwm_samples[1][1]

        second_peak_temp = self.peaks[3][0]
        second_peak_time = self.peaks[3][1]
        pulse_width_second_pulse =  self.pwm_samples[3][0] - self.pwm_samples[2][0]
        pulse_state_second_pulse =  self.pwm_samples[2][1]

        time_to_peak_rising_edge = first_peak_time-self.pwm_samples[1][0]
        time_to_peak_falling_edge = second_peak_time-self.pwm_samples[2][0]
        t_overshoot_up = first_peak_temp-self.target
        t_overshoot_down =  time_to_peak_rising_edge
        coast_time_up = self.target-TUNE_PID_DELTA - second_peak_temp
        coast_time_down = time_to_peak_falling_edge
        logging.info("%s: t_overshoot_up %.3f, coast_time_up %.3f, t_overshoot_down %.3f, coast_time_down %.3f", self.algo_name, t_overshoot_up, coast_time_up, t_overshoot_down, coast_time_down)
        logging.info("%s: actuator duty cycle: %.3f", self.algo_name, pulse_width_second_pulse/(pulse_state_first_pulse + pulse_state_second_pulse))
        #TODO: Look at the time between switching the power off during a rising edge
        # compute t_overshoot_up --> peak temperature above our setpoint.
        # compute t_overshoot_down --> peak temperature below our setpoint-TUNE_PID_DELTA

        duty_cycle = pulse_width_second_pulse / Tu # pulse width divided by the period
        Kss_est =  duty_cycle / self.get_avg_temp(first_off_switch, last_off_switch) # estimated steady state power ratio of max power
        Kss = Kss_est
        # Compute FOWDT model parameters
        omega_u  = (2*math.pi) / Tu # critical frequency
        K = (self.target - TEMP_AMBIENT) / max(duty_cycle, 0.001)
        gain_product = K * Ku

        if gain_product <= 1.0:
            raise logging.error("%s: AutoTune failed measured gain-product is too low.", self.algo_name)
        tau = math.sqrt(gain_product**2 - 1) / omega_u # Time constant
        L = (math.pi - math.atan(omega_u*tau)) / omega_u # Dead time

        ################# Leaving this here for later PID tuning #####################
        #Ti = 0.5 * Tu
        #Td = 0.125 * Tu
        #Kp = 0.6 * Ku * PARAM_BASE
        #Ki = Kp / Ti
        #Kd = Kp * Td
        
        ## Classic Ziegler-Nichols Table
        #Controller,Kc​ (Kp​),   Ti​,        Td​,         Ki​ (Kc​/Ti​),  Kd​ (Kc​⋅Td​)
        #P          0.5 Ku​,    inf,       0,          0,           0
        #PI         0.45 Ku​,   0.83 Tu​,   0,          0.54 Ku​/Tu​,  0
        #PID        0.6 Ku​,    0.5 Tu​,    0.125 Tu​,   1.2 Ku​/Tu​,   0.075Ku​⋅Tu​
        #
        ## Tyreus-Luyben Values -- More conservative than Ziegler-Nichols
        Kp =  0.31*Ku * PARAM_BASE
        Ti =  2.2 *Tu
        Td =  Tu/6.3
        Ki = Kp / Ti
        Kd = Kp * Td
        logging.info("%s: PID Tyreus-Luyben values: Kp: %.3f, Ki: %.3f, Kd: %.3f", self.algo_name, Kp, Ki, Kd)
        
        ## AMIGO method FF+PID Tuning vars:
        # Ms <= 1.4 robustness constraint
        Kc = 1/K * (0.2 + 0.45* tau /L ) * PARAM_BASE
        Ti = L * 0.4 * L + 0.8 * tau / (L + 0.1 * tau)
        Td = 0.5*L * tau / (0.3 * L + tau)
        Kp = Kc
        Ki = Kc / Ti
        Kd = Kc * Td
        logging.info("%s: AMIGO PID values: Kp: %.3f, Ki: %.3f, Kd: %.3f", self.algo_name, Kp, Ki, Kd)

        ## Feed foward controller estimate:
        # Gff(s) =  1 + s * tau / K
        # I use Kss as 1/K
        # u_ff = Kss *( 1 + s*tau )* (Q-filter ) * ref
        # Q_filter = 1 / (1+s*tau_f)
        self.configvars.Kss = Kss
        self.configvars.Ku = Ku
        self.configvars.Tu = Tu
        self.configvars.tau = tau
        self.configvars.L = L
        self.configvars.omega_u = omega_u
        self.configvars.t_overshoot_up = t_overshoot_up
        self.configvars.t_overshoot_down = t_overshoot_down
        self.configvars.coast_time_up = coast_time_up
        self.configvars.coast_time_down = coast_time_down
        self.configvars.Kp = Kp
        self.configvars.Ki = Ki
        self.configvars.Kd = Kd
        return Kss,Ku,Tu,tau,L,omega_u, t_overshoot_up, t_overshoot_down, coast_time_up, coast_time_down, Kp, Ki, Kd


    def calc_final_fowdt(self):
        cycle_times = [(self.peaks[pos][1] - self.peaks[pos-2][1], pos)
                       for pos in range(4, len(self.peaks))]
        midpoint_pos = sorted(cycle_times)[len(cycle_times)//2][1]
        return self.calc_fowdt(midpoint_pos)

    
    # Utility Functions
    def write_file(self, filename):
        pwm = ["pwm: %.3f %.3f" % (time, value)
               for time, value in self.pwm_samples]
        out = ["%.3f %.3f" % (time, temp) for time, temp in self.temp_samples]
        f = open(filename, "w")
        f.write('\n'.join(pwm + out))
        f.close()

    def get_avg_temp(self, t_start, t_end):
        # Filter temps within the time range
        temps = [temp for time, temp in self.temp_samples if t_start <= time <= t_end]
        # Return average, or 0/None if no samples found to avoid DivisionByZero
        logging.info("%s: Average Temp = %.3f", self.algo_name, sum(temps) / len(temps))
        
        return sum(temps) / len(temps) if temps else 0.0


class SSAutoTune:
    def __init__(self, heater, target, Kss):
        self.algo_name = "PP-SS-AutoTune"
        self.configvars = SimpleNamespace()
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
        self.prev_temp = 0.
        self.Kss = Kss
        self.min_duration = 10. # 10 seconds at steady state between recomputing Kss value
        self.slope_threshold = 0.05 # if this is maintained with openloop control we know Kss is acurate at the measured temp
        self.computed_kss = []

        self.hold_start_time = None
        self.holding_pwm = False

    # Heater control 
    def set_pwm(self, read_time, value):
        if value != self.last_pwm: # save each time the pwm is changed
            self.pwm_samples.append(
                (read_time + self.heater.get_pwm_delay(), value))
            self.last_pwm = value
            self.computed_kss.append((read_time + self.heater.get_pwm_delay(), self.Kss))
        self.heater.set_pwm(read_time, value)

    def temperature_update(self, read_time, temp, target_temp):
        self.temp_samples.append((read_time, temp))
        if not self.holding_pwm:
            pwm = max(0.0, min(1.0, target_temp * self.Kss))
            self.set_pwm(read_time, pwm)
            self.hold_start_time = read_time
            self.holding_pwm = True
        else:
            if read_time - self.hold_start_time >= self.min_duration:
                avg_temp_slope = self.get_avg_temp_slope(self.hold_start_time, read_time)
                if abs(avg_temp_slope) > self.slope_threshold:
                    self.Kss = self.compute_steadystate(read_time)
                    pwm = max(0.0, min(1.0, target_temp * self.Kss))
                    self.set_pwm(read_time, pwm)
                    self.hold_start_time = read_time
                # else: keep holding current PWM
        # All logic is event-driven, no blocking or sleep

    def check_busy(self, eventtime, smoothed_temp, target_temp):
        if self.heating or len(self.peaks) < 12:
            return True
        return False
    
    @property
    def steady_state_reached(self):
        if self.holding_pwm and self.hold_start_time is not None:
            avg_temp_slope = self.get_avg_temp_slope(self.hold_start_time, self.hold_start_time + self.min_duration)
            return abs(avg_temp_slope) < self.slope_threshold
        return False

    # Analysis
    def compute_steadystate(self, read_time):
        avg_temp = self.get_avg_temp(read_time-self.min_duration, self.min_duration)
        avg_temp_slope = self.get_avg_temp_slope(read_time-self.min_duration, self.min_duration)
        Kss_calibrated = self.last_pwm/avg_temp
        self.computed_kss.append((read_time, Kss_calibrated))
        return Kss_calibrated   


    
    # Offline analysis helper
    def write_file(self, filename):
        pwm = ["pwm: %.3f %.3f" % (time, value)
               for time, value in self.pwm_samples]
        out = ["%.3f %.3f" % (time, temp) for time, temp in self.temp_samples]
        f = open(filename, "w")
        f.write('\n'.join(pwm + out))
        f.close()

    def get_avg_temp(self, t_start, t_end):
        # Filter temps within the time range
        temps = [temp for time, temp in self.temp_samples if t_start <= time <= t_end]
        # Return average, or 0/None if no samples found to avoid DivisionByZero
        logging.info("%s: Average Temp = %.3f", self.algo_name, sum(temps) / len(temps))
        
        return sum(temps) / len(temps) if temps else 0.0
    
    def get_avg_temp_slope(self, t_start, t_end):
        temps = [temp for time, temp in self.temp_samples if t_start <= time <= t_end]
        if len(temps) < 2:
            return 0.0
        temp_diff = [t2 - t1 for t1, t2 in zip(temps, temps[1:])]
        avg_slope = sum(temp_diff) / len(temp_diff)
        logging.info("%s: Average Temp slope = %.3f", self.algo_name, avg_slope)
        return avg_slope

def load_config(config):
    return PPCalibrate(config)


# TODO: Modify calculations to use ambient temperature --> more important for heated enclosures though
# TODO: DONE, use self.temp_samples average temp between first high peak and last peak times to copute K_ss estimate
# TODO: Add a steady-state calibration test which holds target temp with ss sensitivity value
# -- K_ss should be computed from the average duty cycle and average temperature during htis period
# TODO: K_ss should hold temp within a given Temp_delta, come to a rest and then turn on the part fan
# The temp difference between fan off and fan on is used to compute K_fan
# TODO: Optional K_ev calculation by feeding filament and watching temperature drop.
