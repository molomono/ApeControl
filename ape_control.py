import logging 
import importlib

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        arch_type = config.get('architecture', 'pp_control')
        
        # Logic to dynamically load from the ape_modules folder
        if arch_type == 'pp_control':
            from .control_modules.pp_control import PPControl 
            from .control_modules.pp_calibrate import PPCalibrate
            self.controller = PPControl(config)
            self.printer.add_object('pp_calibrate', PPCalibrate(config)) 
        elif arch_type == 'ss_ff_gain':
            from .control_modules.ss_ff_gain import SSFFControl
            self.controller = SSFFControl(config)
        elif arch_type == 'lead_lag_control':
            from .control_modules.lead_lag_control import LeadLagControl
            self.controller = LeadLagControl(config)
        elif arch_type == 'simple_ff_fb_control':
            from .control_modules.simple_ff_fb_control import SimpleFFFBControl
            self.controller = SimpleFFFBControl(config)
        else:
            logging.error("Unknown architecture type specified: %s. Defaulting to PP-Control." % arch_type)
            from .control_modules.pp_control import PPControl
            self.controller = PPControl(config)

def load_config_prefix(config):
    return ApeControl(config)