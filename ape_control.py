import logging 

class ApeControl:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[1] # (heater) name
        arch_type = config.get('architecture', 'pp_control')
        
        # Logic to dynamically load from the ape_modules folder
        if arch_type == 'pp_control':
            from .control_modules.pp_control import PPControl 
            from .control_modules.pp_calibrate import PPCalibrate
            self.exchange_controller(PPControl(config))
            self.printer.add_object('pp_calibrate', PPCalibrate(config)) 
        elif arch_type == 'mpc-example':
            pass # example line for adding addtional control modules
        else:
            logging.error("Unknown architecture type specified: %s. Defaulting to original Klipper Control algorithm." % arch_type)

    ### This function uses similar logic to the pid_calibrate script, exchanging the existing Controller for one of the ApeControl architectures. 
    # I feel like this should be moved into the BaseController, and forced to be called instead of install_hijack.
    # but that will be a version 2.0 of the base class. leaving it hear for clarity.
    # 
    # The issue is the base-class is the controller which is being exchanged.
    # So ideally it is called outside that context. So this is probably the right location
    # i just need to restructer the "install_hijack" function and monkeypatch.
    # the monkey patch can be converted into a type of safety logic (just a wrapper on the update) to trigger the backup controller.
    # And i guess install_hijack isn't necissary either anymore. The exchange is handeld by ApeControl class.
    def exchange_controller(self, new_controller):
        # load objects
        pheaters =  self.printer.lookup_object('heaters')
        try:
            heater = pheaters.lookup_heater(self.name)
        except
            raise logging.error("Could not find heater: %s with name %s" % (self.name))
        
        old_control = heater.set_control(new_controller) # exchange control objects
        new_controller.backup_control = old_control # store the old control object in the new controller for saftey fallback
        logging.info("ApeControl: Successfully swapped controllers! On heater object '%s'",self.name)
        return new_controller
        

def load_config_prefix(config):
    return ApeControl(config)