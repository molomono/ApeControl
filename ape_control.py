import logging 

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1] # (heater) name
        arch_type = config.get('architecture', 'pp_control')
        self.old_control = None
        
        # Logic to dynamically load from the ape_modules folder
        if arch_type == 'pp_control':
            from .control_modules.pp_control import PPControl 
            from .control_modules.pp_calibrate import PPCalibrate
            self.new_controller = PPControl(config)
            self.printer.add_object('pp_calibrate', PPCalibrate(config)) 
        elif arch_type == 'pid_control':
            from .control_modules.pid_control import PIDControl 
            self.new_controller = PIDControl(config)
            
        elif arch_type == 'mpc-example':
            pass # example line for adding addtional control modules
        else:
            logging.error("Unknown architecture type specified: %s. Defaulting to original Klipper Control algorithm." % arch_type)

        self.printer.register_event_handler("klippy:ready", self.exchange_controller)

    def exchange_controller(self):
        # load objects
        pheaters = self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(self.name)
        except self.printer.config_error as e:
            raise logging.error("%s Heater object could not be found for name %s",str(e), self.name)
    
        self.old_control = heater.set_control(self.new_controller) # exchange control objects
       

def load_config_prefix(config):
    return ApeControl(config)