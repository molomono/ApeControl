import logging 
import importlib

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        arch_type = config.get('architecture', 'pp_control')
        
        # Logic to dynamically load from the ape_modules folder
        if arch_type == 'pp_control':
            from .control_modules.pp_control import PPControl
            self.controller = PPControl(config)
            self.load_custom_object(config, 'pp_calibrate') 
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

    def load_custom_object(self, config, obj_name):
        # Use importlib to reach into your subfolder
        # This assumes ape_control.py and control_modules/ are in the same place
        module_path = f"control_modules.{obj_name}"
        
        try:
            algo_module = importlib.import_module(module_path)
            
            # Manually run the load_config logic
            # (Essentially doing what printer.load_object does, but manually)
            algo_instance = algo_module.load_config(config)
            
            # Register it so it shows up in lookup_object
            self.printer.add_object(obj_name, algo_instance)
        except ImportError as e:
            logging.error(f"ApeControl: Failed to load {obj_name}. Error: {e}")

def load_config_prefix(config):
    return ApeControl(config)