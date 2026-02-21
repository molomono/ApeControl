import logging

class StateLookahead:
    def __init__(self, printer):
        self.printer = printer
        self.toolhead = None
        self.gcode = None
        # Data structure: { 'key': [(planned_time, value), ...] }
        self.state_queues = {}
        
        # We must wait for the printer to be ready to lookup other objects
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_ready(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.gcode = self.printer.lookup_object('gcode')
        
        # Example: Wrap Fan (M106) and Temp (M104)
        # self.wrap_command('M106', 'S', 'fan_speed')
        # self.wrap_command('M104', 'S', 'target_temp')

    def wrap_command(self, cmd_name, param_name, internal_key):
        """Hijacks an existing G-code command while preserving original IO behavior."""
        # Use gcode.handlers.get to find the current function pointer
        prev_handler = self.gcode.handlers.get(cmd_name)
        if not prev_handler:
            return

        self.state_queues[internal_key] = []

        def wrapper(gcmd, *args, **kwargs):
            # 1. Perform our logic (Safe because it's non-blocking)
            val = gcmd.get_float(param_name, None)
            if val is not None:
                planned_time = self.toolhead.get_last_move_time()
                self.state_queues[internal_key].append((planned_time, val))
                self.state_queues[internal_key].sort()
            
            # 2. Call original handler and capture its return value
            # We pass through all args/kwargs to be perfectly transparent
            res = prev_handler(gcmd, *args, **kwargs)
            
            # 3. Respect the original IO
            return res

        # Overwrite the handler in the live dispatch table
        self.gcode.handlers[cmd_name] = wrapper

    def get_state_at(self, internal_key, t_seconds, default_val):
        """
        Returns what the state will be at (read_time + t_seconds).
        """
        if internal_key not in self.state_queues:
            return default_val
            
        now = self.printer.get_reactor().monotonic()
        target_time = now + t_seconds
        queue = self.state_queues[internal_key]

        # 1. Housekeeping: Remove events older than 1 second ago
        self.state_queues[internal_key] = [i for i in queue if i[0] > (now - 1.0)]

        # 2. Find the state at target_time
        # We look for the last event that occurs BEFORE the target_time
        current_resolved_val = default_val
        for event_time, val in queue:
            if event_time <= target_time:
                current_resolved_val = val
            else:
                # This event is further in the future than our lookup
                break
                
        return current_resolved_val