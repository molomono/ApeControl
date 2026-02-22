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
        try:
            pheaters.set_temperature(heater, target, True)
        except self.printer.command_error as e:
            heater.set_control(old_control)
            raise
        heater.set_control(old_control) # Restore actual controller after calibration test
        if write_file:
            calibrate.write_file('/tmp/heattest.txt')
        if calibrate.check_busy(0., 0., 0.):
            raise gcmd.error("pid_calibrate interrupted")
        
        ########## Actual calibraiton logic, data has been collected in ControlAutoTune lists.
        # Log and report results
        Kss,Ku,Tu,tau,L,omega_u = calibrate.calc_final_fowdt()
        #Kp, Ki, Kd = calibrate.calc_final_pid()
        logging.info("PP-AutoTune: Kss=%.3f,Ku=%.3f,Tu=%.3f,omega_u=%.3f,tau=%.3f,L=%.3f", Kss,Ku,Tu,omega_u,tau,L)
        
        gcmd.respond_info(
            "PP-AutoTune: Kss=%.3f,Ku=%.3f,Tu=%.3f,omega_u=%.3f,tau=%.3f,L=%.3f\n"
            "The SAVE_CONFIG command will update the printer config file\n"
            "with these parameters and restart the printer." % (Kss, Ku, Tu, omega_u, tau, L))
        
        # Store results for SAVE_CONFIG
        cfgname = heater.get_name()
        logging.info("PP-AutoTune: %s", cfgname)
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
        self.heater = heater
        self.target = target # used for Kss computation later
        self.heater_max_power = heater.get_max_power()
        self.calibrate_temp = target
        # Heating control
        self.heating = False
        self.peak = 0.
        self.peak_time = 0.
        # Peak recording
        self.peaks = [] # (self.peak, self.peak_time)
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
        #self.calc_pid(len(self.peaks)-1)  # <--- Why is this here

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
        if start_on_peak:
            pulse_width = 1 - self.peaks[pos][1] - self.peaks[pos-1][1]
        else:
            pulse_width = self.peaks[pos][1] - self.peaks[pos-1][1]

        #TODO: Change the above logic to use:
        #self.pwm_samples = (event_time, value)
        # Load these values self.pwm_samples[pos]
        logging.info("PP-Autotuen: pwm_samples: %s", self.pwm_samples)
        # Compute the ratio of on to off time. This is our Kss - sensitivty


        #TODO: Look at the time between switching the power off during a rising edge
        # compute t_overshoot_up --> peak temperature above our setpoint.
        # compute t_overshoot_down --> peak temperature below our setpoint-TUNE_PID_DELTA

        logging.info("PP-AutoTune: Pulse_width: %f ",pulse_width)
        duty_cycle = pulse_width / Tu # pulse width divided by the period
        logging.info("PP-AutoTune: Duty_cycle: %f ",duty_cycle)
        Kss_est =  duty_cycle / self.target # estimated steady state power ratio of max power
        Kss = Kss_est
        logging.info("PP-AutoTune: Kss: %f ",Kss)
        # Compute FOWDT model parameters
        omega_u  = (2*math.pi) / Tu # critical frequency
        logging.info("PP-AutoTune: omega_u: %f ",omega_u)
        K = (self.target - TEMP_AMBIENT) / max(duty_cycle, 0.001)
        logging.info("PP-AutoTune: K=%f", K)
        gain_product = K * Ku
        logging.info("PP-AutoTune: gain_product: %f ",gain_product)
        #if gain_product <= 1.0: # TODO: catch the system if the gain product won't cause FOWDT oscillations
        #    return None
        tau = math.sqrt(gain_product**2 - 1) / omega_u # Time constant
        L = (math.pi - math.atan(omega_u*tau)) / omega_u # Dead time
        
        ################# This section must be changed for FF calibration #####################
        Ti = 0.5 * Tu
        Td = 0.125 * Tu
        Kp = 0.6 * Ku * PARAM_BASE
        Ki = Kp / Ti
        Kd = Kp * Td
        
        return Kss,Ku,Tu,tau,L,omega_u
    
    def calc_final_fowdt(self):
        cycle_times = [(self.peaks[pos][1] - self.peaks[pos-2][1], pos)
                       for pos in range(4, len(self.peaks))]
        midpoint_pos = sorted(cycle_times)[len(cycle_times)//2][1]
        return self.calc_fowdt(midpoint_pos)

    
    def calc_pid(self, pos):
        temp_diff = self.peaks[pos][0] - self.peaks[pos-1][0]
        time_diff = self.peaks[pos][1] - self.peaks[pos-2][1]
        # Use Astrom-Hagglund method to estimate Ku and Tu
        amplitude = .5 * abs(temp_diff)
        Ku = 4. * self.heater_max_power / (math.pi * amplitude)
        Tu = time_diff
        # Use Ziegler-Nichols method to generate PID parameters
        
        ################# This section must be changed for FF calibration #####################
        Ti = 0.5 * Tu
        Td = 0.125 * Tu
        Kp = 0.6 * Ku * PARAM_BASE
        Ki = Kp / Ti
        Kd = Kp * Td
        logging.info("Autotune: raw=%f/%f Ku=%f Tu=%f  Kp=%f Ki=%f Kd=%f",
                     temp_diff, self.heater_max_power, Ku, Tu, Kp, Ki, Kd)
        
        return Kp, Ki, Kd
    
    def calc_final_pid(self):
        cycle_times = [(self.peaks[pos][1] - self.peaks[pos-2][1], pos)
                       for pos in range(4, len(self.peaks))]
        midpoint_pos = sorted(cycle_times)[len(cycle_times)//2][1]
        return self.calc_pid(midpoint_pos)
    
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