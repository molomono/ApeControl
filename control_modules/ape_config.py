class ApeConfig:
    def __init__(self, config, ConfigObject):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        # Common parameters (The "Base" config)
        self.max_power = config.getfloat('max_power', 1.0)
        self.algorithm = config.get('control', 'pid')
        
        # This will hold the specialized config (e.g., PPConfig)
        # It merges the attributes in the ConfigObject with this classes namespace
        self.__dict__.update(ConfigObject(config).__dict__)
        