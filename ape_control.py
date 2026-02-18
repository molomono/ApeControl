class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        arch_type = config.get('architecture', 'pp_control')
        
        # Logic to dynamically load from the ape_modules folder
        if arch_type == 'pp_control':
            from .control_modules import PPControl
            self.controller = PPControl(config)
        
def load_config_prefix(config):
    return ApeControl(config)