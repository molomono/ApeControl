class ApeConfig:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        # Common parameters (The "Base" config)
        self.max_power = config.getfloat('max_power', 1.0)
        self.algorithm = config.get('control', 'pid')
        
        # This will hold the specialized config (e.g., PPConfig)
        # It merges the attributes in the ConfigObject with this classes namespace

    def add_configvars_local(self, configobject):
        """Add config variables to the local ApeConfig namespace"""
        self.__dict__.update(configobject.__dict__)
        
    def add_configvars_ff(self, configobject):
        """Add config variables to the ApeConfig.ff namespace"""
        self.ff = configobject

    def add_configvars_fb(self, configobject):
        """Add config variables to the ApeConfig.fb namespace"""
        self.fb = configobject