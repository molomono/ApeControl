# ApeControl-Klipper Dynamic module/control algorithm loading script
#
# Author and code: Molomono
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging 

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1] # (heater) name
        self.algo = config.get('control', 'pid_control')
        self.old_control = None
        self.new_controller = None

        
    #def controller_lookup(self,config):
        # Logic to dynamically load from the ape_modules folder
        if self.algo == 'pp_control':
            from .control_modules.pp_calibrate import PPCalibrate
            self.printer.add_object('pp_calibrate', PPCalibrate(config)) # must import this before the controller
            from .control_modules.pp_control import PPControl 
            self.new_controller = PPControl(config)
        elif self.algo == 'pid_control':
            from .control_modules.pid_control import PIDControl 
            self.new_controller = PIDControl(config)
        elif self.algo == 'mpc':
            from .control_modules.mpc_control import ControlMPC 
            self.new_controller = ControlMPC(config)
        else:
            logging.error("Unknown architecture type specified: %s. Defaulting to original Klipper Control algorithm.", self.algo)

        self.printer.register_event_handler("klippy:connect", self.switch_controllers)


    def switch_controllers(self):
        # Following lookups are becoming obsolete
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(self.name)
            self.new_controller._heater = heater
            self.old_control = heater.set_control(self.new_controller)
            logging.info("ApeControl: Heater object '%s' controller exchanged with %s algorithm", self.name, self.algo)
        except self.printer.config_error as e:
            logging.error("ApeControl: %s Heater object could not be found for name %s", str(e), self.name)        
            raise e

def load_config_prefix(config):
    return ApeControl(config)



## Monkey patches so far:
# printer.wait_while() --> conditional wait statement attached to the pritner during MPC calibrate
# printer.