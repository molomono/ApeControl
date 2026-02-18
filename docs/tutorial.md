# ApeControl Tutorial: Extending Temperature Control in Klipper

This tutorial demonstrates how to extend ApeControl with custom temperature controllers.

## Overview

ApeControl provides a framework for creating advanced temperature controllers that integrate with Klipper's PID system through monkey patching. The key components are:

- **BaseController**: Handles monkey patching and provides common functionality
- **Control Modules**: Your custom algorithms (like PPControl, LeadLagControl)
- **Configuration**: Klipper config sections that load your controllers

## Key Features Demonstrated

### 1. Monkey Patching Integration
ApeControl hijacks Klipper's `ControlPID.temperature_update()` method, allowing you to:
- Access the original PID's internal states
- Capture the PID's computed PWM output
- Maintain compatibility with Klipper's temperature management
- Create control algorithms without modifying the mainline klipper code

### 2. Feed-Forward + Feedback Control
Modern Industrial control often combines:
- **Feed-forward**: Predicts required output based on model knowledge
    - Fast-acting, "Proactive" responding to controller inputs.
    - No temperature measurement means its performance is directly tied to model-knowledge.
- **Feedback**: Corrects errors using measurements
    - Slow-acting, "Reactive" responds to error between setpoint and true value.
    - Can remove linear Steady State errors.
    - Simple FB controlelrs require very little model knowledge. (PID)

### 3. Advanced control
Advanced control is generally overkill for generic temperature regulation. But let's be honest, the rule of cool applies here. So let's outline some algorithms that could be categorized as "Advanced".
- **(Model) Predictive control** (MPC)
- **Learning control** (Q-learning, Iterative Feed Forward learning control, Transfer Learning)
- **Adaptive control** (Model Reference Adapative Control, Online-Parameter Estimation, Adaptive Output Feedback control)
- **Non-linear Control** (Feedback Linearization, Backstepping, Fuzzy Logic Control)
- **Optimal (Robust) Control** (H2/Hinf Control, Linear Quadratic Gaussian, Linear Quadratic Regulator)
- etc.
## Creating Your Own Controller

### Step 1: Create the Class

```python
import logging
from .base_controller import BaseController

class MyControl(BaseController):
    def __init__(self, config):
        super().__init__(config)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        # Load your parameters
        self.my_param = config.getfloat('my_param', 1.0)
        
    def handle_ready(self):
        self.install_hijack()
        
    def compute_control(self, pid_self, read_time, temp, target_temp):
        # Always call this first!
        self.orig_temp_update(read_time, temp, target_temp)
        
        if target_temp == 0:
            return 0.0
            
        # Your algorithm here
        error = target_temp - temp
        output = self.my_param * error
        
        logging.info("MyController: Unclamped output power %.3f" % (output))

        return output  # Base class handles clamping
```

### Step 2: Register with ApeControl in ape_control.py

Add your controller to the match-case statement:

```python
elif arch_type == 'my_control':
    from .control_modules.my_control import MyControl
    self.controller = MyControl(config)
```

This is the **only file you need to modify** for your controller to work.

*(Optional: You can also add `from .my_control import MyControl` to `control_modules/__init__.py` for convenience, but this is not required.)*

### Step 3: Configure in printer.cfg

```ini
[my_control my_heater]
architecture: my_control
my_param: 2.0
```

### Step 4: Monitor controller behavior.
1. SSH into your existing klipper host machine.
2. Run the tail -f command with the | grep "String to Look for" 
- This will look into the klippy log and print the logging output to the terminal in real time. Giving you the power to see what is happening inside your classes and debug issues.

```bash
ssh user@klipperhost
tail -f ~/printer_data/logs/klippy.log | grep "MyController"
```
- Note: If klippy hangs at disconnected it might be caused by your python script crashing. Remove the | grep statement of the command and restart klippy. It will print the standard python crash information if this is relevant. 



### Step 5: (Optional) Design a Calibration script.

```python
TODO... 
```


## Example Controllers

### Simple Feed-Forward + Feedback

```python
class SimpleFFFB(BaseController):
    def __init__(self, config):
        super().__init__(config)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self.k_ff = config.getfloat('k_ff', 0.01)  # Feed-forward gain
        self.k_fb = config.getfloat('k_fb', 0.5)   # Feedback gain
        
    def handle_ready(self):
        self.install_hijack()
        
    def compute_control(self, pid_self, read_time, temp, target_temp):
        self.orig_temp_update(read_time, temp, target_temp)
        
        if target_temp == 0:
            return 0.0
            
        ff_term = self.k_ff * target_temp
        fb_term = self.k_fb * self.captured_fb_pwm
        
        return ff_term + fb_term
```

### State Machine Controller

```python
class StateMachineControl(BaseController):
    def __init__(self, config):
        super().__init__(config)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        
        self.state = "off"
        self.states = {
            "off": self._state_off,
            "heating": self._state_heating,
            "regulating": self._state_regulating
        }
        
    def handle_ready(self):
        self.install_hijack()
        
    def compute_control(self, pid_self, read_time, temp, target_temp):
        self.orig_temp_update(read_time, temp, target_temp)
        
        error = target_temp - temp
        return self.states[self.state](error, target_temp)
        
    def _state_off(self, error, target_temp):
        if target_temp > 0:
            self.state = "heating"
        return 0.0
        
    def _state_heating(self, error, target_temp):
        if abs(error) < 5:
            self.state = "regulating"
        return 1.0
        
    def _state_regulating(self, error, target_temp):
        return self.captured_fb_pwm  # Use original PID
```

## Advanced Features

### Accessing Captured PID Output

```python
def compute_control(self, pid_self, read_time, temp, target_temp):
    self.orig_temp_update(read_time, temp, target_temp)
    
    pid_output = self.captured_fb_pwm  # Original PID's PWM
    # Use in your algorithm...
```

### Custom Parameters

Load any parameters you need:
```python
self.gains = config.getfloatlist('gains', [1.0, 2.0, 3.0])
self.time_constants = config.getfloatlist('time_constants', [10.0, 20.0])
```

# In Summary
## Best Practices

1. **Always call `self.orig_temp_update()` first** - Maintains PID state
2. **Handle target_temp == 0** - Off state
3. **Use logging** - Debug your algorithms
4. **Register 'klippy:ready' handler** - Ensures proper initialization order

## Testing Your Controller

1. Start with simple algorithms
2. Use logging to monitor behavior
3. Test heating and cooling scenarios
4. Verify state transitions (if using state machines)
5. Check that captured PID values are reasonable

## Integration with Klipper

Your controllers work alongside Klipper's:
- Temperature sensors
- Safety limits
- G-code commands
- Status reporting

The monkey patching is transparent to Klipper's core functionality.