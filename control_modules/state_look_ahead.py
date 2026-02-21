import logging

class StateLookahead:
    def __init__(self, printer):
        self.printer = printer
        self.toolhead = printer.lookup_object('toolhead')
        self.gcode = printer.lookup_object('gcode')
        # Dictionary of deques: { 'extruder_temp': [(time, value), ...], 'fan_speed': [...] }
        self.queues = {}

    def register_intercept(self, command, param_name, internal_key, type_conv=float):
        """
        command: The G-code (e.g., 'M106')
        param_name: The G-code parameter (e.g., 'S')
        internal_key: Your reference name (e.g., 'fan_speed')
        """
        self.queues[internal_key] = []
        
        def handle_command(gcmd):
            # 1. Get the value from the G-code
            val = gcmd.get(param_name, None)
            if val is not None:
                val = type_conv(val)
                # 2. Get the "Future Time" (End of the lookahead queue)
                # This is the time the hardware actually reaches this G-code line
                planned_time = self.toolhead.get_last_move_time()
                
                # 3. Store in our local buffer
                self.queues[internal_key].append((planned_time, val))
                self.queues[internal_key].sort() # Ensure time-ordered

            # 4. CRITICAL: Dispatch to original Klipper handlers so hardware actually moves
            # We use the underlying gcode dispatch logic to avoid infinite loops
            prev_handler = self.gcode.base_handlers.get(command)
            if prev_handler:
                prev_handler(gcmd)

        self.gcode.register_command(command, handle_command)

    def get_state_at(self, internal_key, future_time_offset, current_val):
        """
        Queries what the state will be at (now + future_time_offset)
        """
        now = self.printer.get_reactor().monotonic()

        target_time = now + future_time_offset
        queue = self.queues.get(internal_key, [])
        
        # Clean up expired entries (older than current time)
        self.queues[internal_key] = [i for i in queue if i[0] > now - 1.0]

        # Find the last entry that occurs BEFORE or AT our target_time
        last_known_val = current_val
        for event_time, val in queue:
            if event_time <= target_time:
                last_known_val = val
            else:
                break
        return last_known_val