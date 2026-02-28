class ApeConfig:
    def __init__(self, config, ConfigObject):
        self.printer = config.get_printer()
        # Common parameters (The "Base" config)
        self.max_power = config.getfloat('max_power', 1.0)
        self.algorithm = config.get('control', 'pid')
        
        # This will hold the specialized config (e.g., PPConfig)
        self.config_params = ConfigObject(config)

    #def load_params(self, config, configObject):
        # Explicitly defining the namespace
    #    self.algo_vars = configObject(config) 