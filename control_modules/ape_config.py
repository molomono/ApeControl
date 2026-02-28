# At the very top of your ape_control.py
from .pp_control import PPControl
from .pid_control import PIDControl
from .mpc_control import ControlMPC

# The Registry
ALGO_MAP = {
    "pp": PPControl,
    "pid": PIDControl,
    "mpc": ControlMPC
}

class ApeConfig:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.heater_name = config.get_name().split()[-1]
        # Common parameters (The "Base" config)
        self.max_power = config.getfloat('max_power', 1.0)
        self.algorithm = config.get('control', 'pid')
        
        # FeedForward and FeedBack namespaces
        self.ff = None
        self.fb = None
        
    # Add ConfigVar methods
    def add_configvars_local(self, configobject):
        """Add config variables to the local ApeConfig namespace"""
        self.__dict__.update(configobject.__dict__)
        
    def add_configvars_ff(self, configobject):
        """Add config variables to the ApeConfig.ff namespace"""
        self.ff = configobject

    def add_configvars_fb(self, configobject):
        """Add config variables to the ApeConfig.fb namespace"""
        self.fb = configobject

    # Constructor fo loaded control algos
    def construct_controller(self, algorithm = None):
        """Construct Control Object from current parameters"""
        if algorithm is None:
            ControllerClass = ALGO_MAP.get(self.algorithm)
        else:
            ControllerClass = ALGO_MAP.get(algorithm)

        if ControllerClass is None:
            raise self.printer.config_error(
                f"ApeControl: Algorithm '{self.algorithm}' not recognized. "
                f"Available: {list(ALGO_MAP.keys())}")
        
        return ControllerClass(self)