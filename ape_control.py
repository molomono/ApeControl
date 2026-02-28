# ApeControl-Klipper Dynamic module/control algorithm loading script
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging 
from .control_modules.ape_config import ApeConfig

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1] # (heater) name
        self.algo = config.get('control', 'pid')
        self.old_control = None

        
        # Logic to dynamically load from the ape_modules folder
        if self.algo == 'pp':
            from .control_modules.pp_calibrate import PPCalibrate
            self.printer.add_object('pp_calibrate', PPCalibrate(config)) # must import this before the controller
            
            from .control_modules.pp_control import PPControl, PPConfig 
            from .control_modules.pid_control import PIDConfig
            self.apeconfig = ApeConfig(config)
            logging.info("ApeControl: PP config loaded")
            self.apeconfig.add_configvars_ff(PPConfig(config))
            logging.info("ApeControl: PID config loaded")
            self.apeconfig.add_configvars_fb(PIDConfig(config))
            #logging.info("ApeControl: PP object found")
            #self.ControllerClass = PPControl

        elif self.algo == 'pid':
            from .control_modules.pid_control import PIDConfig
            self.apeconfig = ApeConfig(config)
            self.apeconfig.add_configvars_fb(PIDConfig(config))
            logging.info("ApeControl: PID config loaded")

            #logging.info("ApeControl: PID object found")
        elif self.algo == 'mpc':
            from .control_modules.mpc_control import MPCConfig
            self.apeconfig = ApeConfig(config)
            self.apeconfig.add_configvars_local(MPCConfig(config))
            #self.new_controller = ControlMPC(config)
        else:
            logging.error("Unknown architecture type specified: %s. Defaulting to original Klipper Control algorithm.", self.algo)
        
        self.printer.register_event_handler("klippy:connect", self.exchange_controller)

    def exchange_controller(self):
        # load objects
        logging.info("ApeControl: klippy:connect called")
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(self.name)
            logging.info("ApeControl: Heater object found")
            #self.new_controller = self.ControllerClass(self.apeconfig)
            self.new_controller = self.apeconfig.construct_controller(self.algo)
            logging.info("ApeControl: Controller built")
            self.old_control = heater.set_control(self.new_controller) # exchange control objects
            try:
                self.new_controller.post_init() # if there is a post_init script run it now
            except:
                pass
            logging.info("ApeControl: Heater object '%s' controller exchanged with %s algorithm", self.name, self.algo)
        except self.printer.config_error as e:
            logging.error("ApeControl: %s Heater object could not be found for name %s", str(e), self.name)        
            raise e

def load_config_prefix(config):
    return ApeControl(config)



## Monkey patches so far:
# printer.wait_while() --> conditional wait statement attached to the pritner during MPC calibrate
# printer.