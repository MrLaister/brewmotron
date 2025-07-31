"""
Hardware Abstraction Layer for Testing

Comprehensive hardware simulation framework for testing Brewmotron plugins
that interface with GPIO, I2C, and other hardware components.
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Callable, Any, Union
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

# =============================================================================
# Hardware State Management
# =============================================================================

@dataclass
class GPIOPinState:
    """State of a single GPIO pin."""
    mode: Optional[int] = None  # GPIO.IN, GPIO.OUT
    value: int = 0  # GPIO.HIGH, GPIO.LOW
    pull_up_down: Optional[int] = None
    last_change: datetime = field(default_factory=datetime.now)
    interrupt_callback: Optional[Callable] = None
    bounce_time: int = 200  # ms

@dataclass
class I2CDeviceState:
    """State of an I2C device."""
    address: int
    registers: Dict[int, int] = field(default_factory=dict)
    connected: bool = True
    response_delay: float = 0.001  # seconds
    last_access: datetime = field(default_factory=datetime.now)

@dataclass  
class SensorReading:
    """Sensor reading with metadata."""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    unit: str = "C"
    quality: float = 1.0  # 0-1, measurement quality
    error: Optional[str] = None

# =============================================================================
# GPIO Hardware Simulation
# =============================================================================

class MockRPiGPIO:
    """Advanced mock of RPi.GPIO with realistic behavior simulation."""
    
    # GPIO Constants
    BCM = 11
    BOARD = 10
    IN = 1
    OUT = 0
    HIGH = 1
    LOW = 0
    PUD_UP = 22
    PUD_DOWN = 21
    PUD_OFF = 20
    RISING = 31
    FALLING = 32
    BOTH = 33
    
    def __init__(self):
        self._mode = None
        self._pins: Dict[int, GPIOPinState] = {}
        self._warnings = True
        self._interrupt_threads: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}
        
        # Simulation parameters
        self._noise_level = 0.0  # 0-1, electrical noise simulation
        self._power_supply_voltage = 3.3  # Volts
        
        logger.debug("MockRPiGPIO initialized")
    
    def setmode(self, mode: int) -> None:
        """Set GPIO pin numbering mode."""
        if self._mode is not None and self._mode != mode:
            if self._warnings:
                logger.warning("GPIO mode already set")
        self._mode = mode
        logger.debug(f"GPIO mode set to {mode}")
    
    def getmode(self) -> Optional[int]:
        """Get current GPIO pin numbering mode."""
        return self._mode
    
    def setup(self, pin: Union[int, List[int]], mode: int, 
              pull_up_down: int = PUD_OFF, initial: int = LOW) -> None:
        """Setup GPIO pin(s)."""
        pins = [pin] if isinstance(pin, int) else pin
        
        for p in pins:
            if p in self._pins:
                logger.warning(f"Pin {p} already set up")
            
            self._pins[p] = GPIOPinState(
                mode=mode,
                value=initial if mode == self.OUT else self.LOW,
                pull_up_down=pull_up_down
            )
            
            logger.debug(f"Pin {p} setup: mode={mode}, pull_up_down={pull_up_down}, initial={initial}")
    
    def output(self, pin: Union[int, List[int]], value: Union[int, List[int]]) -> None:
        """Set output value for pin(s)."""
        pins = [pin] if isinstance(pin, int) else pin
        values = [value] if isinstance(value, int) else value
        
        if len(values) == 1 and len(pins) > 1:
            values = values * len(pins)
        
        for p, v in zip(pins, values):
            if p not in self._pins:
                raise RuntimeError(f"Pin {p} not set up")
            
            pin_state = self._pins[p]
            if pin_state.mode != self.OUT:
                raise RuntimeError(f"Pin {p} not set up as output")
            
            # Simulate some electrical characteristics
            old_value = pin_state.value
            pin_state.value = v
            pin_state.last_change = datetime.now()
            
            # Trigger interrupt simulation if value changed
            if old_value != v and pin_state.interrupt_callback:
                self._trigger_interrupt(p, v)
            
            logger.debug(f"Pin {p} output set to {v}")
    
    def input(self, pin: int) -> int:
        """Read input value from pin."""
        if pin not in self._pins:
            raise RuntimeError(f"Pin {pin} not set up")
        
        pin_state = self._pins[pin]
        
        # Simulate electrical noise
        if self._noise_level > 0:
            noise = random.random() < self._noise_level
            if noise:
                return 1 - pin_state.value  # Flip value due to noise
        
        # Simulate pull-up/pull-down behavior
        if pin_state.mode == self.IN:
            if pin_state.pull_up_down == self.PUD_UP:
                return self.HIGH
            elif pin_state.pull_up_down == self.PUD_DOWN:
                return self.LOW
        
        return pin_state.value
    
    def add_event_detect(self, pin: int, edge: int, callback: Optional[Callable] = None,
                        bouncetime: int = 200) -> None:
        """Add edge detection for pin."""
        if pin not in self._pins:
            raise RuntimeError(f"Pin {pin} not set up")
        
        pin_state = self._pins[pin]
        pin_state.interrupt_callback = callback
        pin_state.bounce_time = bouncetime
        
        logger.debug(f"Edge detection added for pin {pin}, edge={edge}")
    
    def remove_event_detect(self, pin: int) -> None:
        """Remove edge detection for pin."""
        if pin in self._pins:
            self._pins[pin].interrupt_callback = None
        
        if pin in self._interrupt_threads:
            self._stop_events[pin].set()
            self._interrupt_threads[pin].join()
            del self._interrupt_threads[pin]
            del self._stop_events[pin]
        
        logger.debug(f"Edge detection removed for pin {pin}")
    
    def event_detected(self, pin: int) -> bool:
        """Check if event was detected on pin."""
        # Simple implementation - in real hardware this would be more complex
        return False
    
    def wait_for_edge(self, pin: int, edge: int, bouncetime: int = 200, 
                     timeout: int = -1) -> Optional[int]:
        """Wait for edge on pin."""
        # Simplified implementation for testing
        if timeout > 0:
            time.sleep(timeout / 1000.0)
        return pin
    
    def cleanup(self, pin: Optional[Union[int, List[int]]] = None) -> None:
        """Clean up GPIO resources."""
        if pin is None:
            # Clean up all pins
            pins_to_clean = list(self._pins.keys())
        elif isinstance(pin, int):
            pins_to_clean = [pin]
        else:
            pins_to_clean = pin
        
        for p in pins_to_clean:
            if p in self._pins:
                del self._pins[p]
            if p in self._interrupt_threads:
                self._stop_events[p].set()
                self._interrupt_threads[p].join()
                del self._interrupt_threads[p]
                del self._stop_events[p]
        
        logger.debug(f"GPIO cleanup completed for pins: {pins_to_clean}")
    
    def setwarnings(self, enabled: bool) -> None:
        """Enable/disable GPIO warnings."""
        self._warnings = enabled
    
    def _trigger_interrupt(self, pin: int, value: int) -> None:
        """Trigger interrupt callback for pin."""
        pin_state = self._pins[pin]
        if pin_state.interrupt_callback:
            # Run callback in separate thread to simulate hardware interrupt
            def run_callback():
                time.sleep(pin_state.bounce_time / 1000.0)  # Debounce delay
                pin_state.interrupt_callback(pin)
            
            thread = threading.Thread(target=run_callback)
            thread.daemon = True
            thread.start()
    
    def simulate_input_change(self, pin: int, value: int) -> None:
        """Simulate external input change (for testing)."""
        if pin in self._pins:
            pin_state = self._pins[pin]
            old_value = pin_state.value
            pin_state.value = value
            pin_state.last_change = datetime.now()
            
            if old_value != value and pin_state.interrupt_callback:
                self._trigger_interrupt(pin, value)
            
            logger.debug(f"Simulated input change on pin {pin}: {old_value} -> {value}")
    
    def set_noise_level(self, level: float) -> None:
        """Set electrical noise simulation level (0-1)."""
        self._noise_level = max(0.0, min(1.0, level))
        logger.debug(f"GPIO noise level set to {self._noise_level}")
    
    def get_pin_state(self, pin: int) -> Optional[GPIOPinState]:
        """Get pin state (for testing)."""
        return self._pins.get(pin)

# =============================================================================
# I2C Hardware Simulation
# =============================================================================

class MockSMBus:
    """Advanced mock of SMBus with realistic I2C behavior simulation."""
    
    def __init__(self, bus_id: int = 1):
        self.bus_id = bus_id
        self._devices: Dict[int, I2CDeviceState] = {}
        self._bus_lock = threading.Lock()
        self._transaction_count = 0
        
        # Simulate some common I2C devices
        self._setup_default_devices()
        
        logger.debug(f"MockSMBus initialized on bus {bus_id}")
    
    def _setup_default_devices(self) -> None:
        """Setup default I2C devices commonly used in Brewmotron."""
        # HT16K33 7-segment displays (0x70-0x76)
        for addr in range(0x70, 0x77):
            self._devices[addr] = I2CDeviceState(
                address=addr,
                registers={
                    0x21: 0x01,  # System setup
                    0xEF: 0x00,  # Display setup
                    0x81: 0x01,  # Brightness
                }
            )
        
        # ADS1115 ADC (0x48)
        self._devices[0x48] = I2CDeviceState(
            address=0x48,
            registers={
                0x00: 0x0000,  # Conversion register
                0x01: 0x0583,  # Config register
                0x02: 0x8000,  # Lo_thresh register
                0x03: 0x7FFF,  # Hi_thresh register
            }
        )
        
        # Generic LCD controller (0x27)
        self._devices[0x27] = I2CDeviceState(
            address=0x27,
            registers={}
        )
    
    def read_byte(self, addr: int) -> int:
        """Read a single byte from I2C device."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate read delay
            time.sleep(device.response_delay)
            device.last_access = datetime.now()
            
            # Return first register value or 0
            return next(iter(device.registers.values())) if device.registers else 0
    
    def write_byte(self, addr: int, value: int) -> None:
        """Write a single byte to I2C device."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate write delay
            time.sleep(device.response_delay)
            device.last_access = datetime.now()
            
            logger.debug(f"I2C write_byte: addr=0x{addr:02X}, value=0x{value:02X}")
    
    def read_byte_data(self, addr: int, reg: int) -> int:
        """Read byte from specific register."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate read delay
            time.sleep(device.response_delay)
            device.last_access = datetime.now()
            
            value = device.registers.get(reg, 0)
            logger.debug(f"I2C read_byte_data: addr=0x{addr:02X}, reg=0x{reg:02X} -> 0x{value:02X}")
            return value
    
    def write_byte_data(self, addr: int, reg: int, value: int) -> None:
        """Write byte to specific register."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate write delay
            time.sleep(device.response_delay)
            device.last_access = datetime.now()
            
            device.registers[reg] = value
            logger.debug(f"I2C write_byte_data: addr=0x{addr:02X}, reg=0x{reg:02X}, value=0x{value:02X}")
    
    def read_word_data(self, addr: int, reg: int) -> int:
        """Read word (2 bytes) from specific register."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate read delay
            time.sleep(device.response_delay * 2)
            device.last_access = datetime.now()
            
            # Read low and high bytes
            low_byte = device.registers.get(reg, 0)
            high_byte = device.registers.get(reg + 1, 0)
            value = (high_byte << 8) | low_byte
            
            logger.debug(f"I2C read_word_data: addr=0x{addr:02X}, reg=0x{reg:02X} -> 0x{value:04X}")
            return value
    
    def write_word_data(self, addr: int, reg: int, value: int) -> None:
        """Write word (2 bytes) to specific register."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate write delay
            time.sleep(device.response_delay * 2)
            device.last_access = datetime.now()
            
            # Split into low and high bytes
            low_byte = value & 0xFF
            high_byte = (value >> 8) & 0xFF
            
            device.registers[reg] = low_byte
            device.registers[reg + 1] = high_byte
            
            logger.debug(f"I2C write_word_data: addr=0x{addr:02X}, reg=0x{reg:02X}, value=0x{value:04X}")
    
    def read_i2c_block_data(self, addr: int, reg: int, length: int) -> List[int]:
        """Read block of data from I2C device."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate read delay
            time.sleep(device.response_delay * length)
            device.last_access = datetime.now()
            
            # Read sequential registers
            data = []
            for i in range(length):
                data.append(device.registers.get(reg + i, 0))
            
            logger.debug(f"I2C read_i2c_block_data: addr=0x{addr:02X}, reg=0x{reg:02X}, length={length}")
            return data
    
    def write_i2c_block_data(self, addr: int, reg: int, data: List[int]) -> None:
        """Write block of data to I2C device."""
        with self._bus_lock:
            self._transaction_count += 1
            device = self._get_device(addr)
            
            # Simulate write delay
            time.sleep(device.response_delay * len(data))
            device.last_access = datetime.now()
            
            # Write to sequential registers
            for i, value in enumerate(data):
                device.registers[reg + i] = value
            
            logger.debug(f"I2C write_i2c_block_data: addr=0x{addr:02X}, reg=0x{reg:02X}, data={data}")
    
    def _get_device(self, addr: int) -> I2CDeviceState:
        """Get or create I2C device."""
        if addr not in self._devices:
            # Create new device if not exists
            self._devices[addr] = I2CDeviceState(address=addr)
            logger.debug(f"Created new I2C device at address 0x{addr:02X}")
        
        device = self._devices[addr]
        
        # Simulate device not responding
        if not device.connected:
            raise OSError(f"I2C device at address 0x{addr:02X} not responding")
        
        return device
    
    def close(self) -> None:
        """Close SMBus connection."""
        logger.debug(f"SMBus closed (transactions: {self._transaction_count})")
    
    def set_device_connected(self, addr: int, connected: bool) -> None:
        """Set device connection status (for testing)."""
        if addr in self._devices:
            self._devices[addr].connected = connected
            logger.debug(f"Device 0x{addr:02X} connection status: {connected}")
    
    def get_device_registers(self, addr: int) -> Dict[int, int]:
        """Get device register contents (for testing)."""
        return self._devices.get(addr, I2CDeviceState(addr)).registers.copy()
    
    def get_transaction_count(self) -> int:
        """Get total I2C transaction count (for testing)."""
        return self._transaction_count

# =============================================================================
# Temperature Sensor Simulation
# =============================================================================

class MockTemperatureSensor:
    """Realistic temperature sensor simulation."""
    
    def __init__(self, base_temperature: float = 20.0, sensor_type: str = "DS18B20"):
        self.base_temperature = base_temperature
        self.sensor_type = sensor_type
        self.current_temperature = base_temperature
        
        # Sensor characteristics
        self.accuracy = 0.5  # °C
        self.resolution = 0.0625  # °C (12-bit)
        self.noise_level = 0.1  # °C RMS
        self.drift_rate = 0.01  # °C per hour
        self.response_time = 0.75  # seconds (63% response)
        
        # Internal state
        self._target_temperature = base_temperature
        self._last_update = datetime.now()
        self._readings_history: List[SensorReading] = []
        
        logger.debug(f"MockTemperatureSensor initialized: {sensor_type}, base={base_temperature}°C")
    
    def set_target_temperature(self, temperature: float) -> None:
        """Set target temperature for simulation."""
        self._target_temperature = temperature
        logger.debug(f"Temperature sensor target set to {temperature}°C")
    
    def read_temperature(self) -> float:
        """Read temperature with realistic sensor behavior."""
        now = datetime.now()
        dt = (now - self._last_update).total_seconds()
        self._last_update = now
        
        # Simulate temperature response curve (first-order)
        tau = self.response_time
        alpha = 1 - math.exp(-dt / tau) if tau > 0 else 1
        
        # Move towards target temperature
        temp_diff = self._target_temperature - self.current_temperature
        self.current_temperature += alpha * temp_diff
        
        # Add sensor noise
        noise = random.gauss(0, self.noise_level)
        measured_temp = self.current_temperature + noise
        
        # Add long-term drift
        drift = self.drift_rate * random.gauss(0, 1) * dt / 3600  # per hour
        measured_temp += drift
        
        # Apply resolution limits
        measured_temp = round(measured_temp / self.resolution) * self.resolution
        
        # Create reading record
        reading = SensorReading(
            value=measured_temp,
            timestamp=now,
            unit="C",
            quality=1.0 - abs(noise) / (3 * self.noise_level)  # Quality based on noise
        )
        
        self._readings_history.append(reading)
        
        # Keep history limited
        if len(self._readings_history) > 1000:
            self._readings_history = self._readings_history[-1000:]
        
        logger.debug(f"Temperature reading: {measured_temp:.2f}°C (target: {self._target_temperature:.2f}°C)")
        return measured_temp
    
    def get_reading_history(self, count: int = 100) -> List[SensorReading]:
        """Get recent temperature readings."""
        return self._readings_history[-count:]
    
    def simulate_sensor_failure(self, failure_type: str = "disconnected") -> None:
        """Simulate sensor failure conditions."""
        if failure_type == "disconnected":
            # Simulate disconnected sensor (often returns 85°C or -127°C)
            self.current_temperature = 85.0
        elif failure_type == "short_circuit":
            # Simulate short circuit (often returns 0°C)
            self.current_temperature = 0.0
        elif failure_type == "high_noise":
            # Increase noise level
            self.noise_level = 5.0
        
        logger.debug(f"Simulated sensor failure: {failure_type}")
    
    def reset_sensor(self) -> None:
        """Reset sensor to normal operation."""
        self.current_temperature = self.base_temperature
        self._target_temperature = self.base_temperature
        self.noise_level = 0.1
        logger.debug("Temperature sensor reset to normal operation")

# =============================================================================
# Display Hardware Simulation
# =============================================================================

class Mock7SegmentDisplay:
    """Mock 7-segment display with state tracking."""
    
    def __init__(self, address: int = 0x70):
        self.address = address
        self.brightness = 15  # 0-15
        self.blink_rate = 0  # 0-3
        self.display_buffer = [0, 0, 0, 0]  # 4 digits
        self.colon = False
        self.enabled = False
        
        logger.debug(f"Mock7SegmentDisplay initialized at address 0x{address:02X}")
    
    def fill(self, value: int) -> None:
        """Fill all digits with same value."""
        self.display_buffer = [value] * 4
        logger.debug(f"7-seg display filled with {value}")
    
    def print(self, value: Union[str, int, float]) -> None:
        """Print value to display."""
        if isinstance(value, (int, float)):
            # Convert number to display format
            str_value = f"{value:4.1f}" if isinstance(value, float) else f"{value:4d}"
        else:
            str_value = str(value)
        
        # Convert to segment codes (simplified)
        for i, char in enumerate(str_value[:4]):
            if char.isdigit():
                self.display_buffer[i] = int(char)
            elif char == '.':
                # Set decimal point on previous digit
                if i > 0:
                    self.display_buffer[i-1] |= 0x80
        
        logger.debug(f"7-seg display shows: {str_value}")
    
    def show(self) -> None:
        """Update display (in real hardware, sends data over I2C)."""
        logger.debug(f"7-seg display updated: {self.display_buffer}")
    
    def set_brightness(self, brightness: int) -> None:
        """Set display brightness (0-15)."""
        self.brightness = max(0, min(15, brightness))
        logger.debug(f"7-seg brightness set to {self.brightness}")
    
    def set_blink_rate(self, rate: int) -> None:
        """Set blink rate (0=off, 1=2Hz, 2=1Hz, 3=0.5Hz)."""
        self.blink_rate = max(0, min(3, rate))
        logger.debug(f"7-seg blink rate set to {self.blink_rate}")
    
    def get_display_state(self) -> Dict[str, Any]:
        """Get current display state (for testing)."""
        return {
            'address': self.address,
            'brightness': self.brightness,
            'blink_rate': self.blink_rate,
            'display_buffer': self.display_buffer.copy(),
            'colon': self.colon,
            'enabled': self.enabled
        }

class MockLCDisplay:
    """Mock LCD character display with state tracking."""
    
    def __init__(self, address: int = 0x27, cols: int = 20, rows: int = 4):
        self.address = address
        self.cols = cols
        self.rows = rows
        self.display_buffer = [[' ' for _ in range(cols)] for _ in range(rows)]
        self.cursor_pos = (0, 0)
        self.cursor_visible = False
        self.blink_cursor = False
        self.backlight = True
        
        logger.debug(f"MockLCDisplay initialized: {cols}x{rows} at address 0x{address:02X}")
    
    def write_string(self, text: str, col: int = None, row: int = None) -> None:
        """Write string to display at specified position."""
        if col is not None and row is not None:
            self.cursor_pos = (row, col)
        
        current_row, current_col = self.cursor_pos
        
        for char in text:
            if char == '\n':
                current_row += 1
                current_col = 0
            elif char == '\r':
                current_col = 0
            else:
                if current_row < self.rows and current_col < self.cols:
                    self.display_buffer[current_row][current_col] = char
                    current_col += 1
                    
                    if current_col >= self.cols:
                        current_row += 1
                        current_col = 0
        
        self.cursor_pos = (current_row, current_col)
        logger.debug(f"LCD write: '{text}' at ({row}, {col})")
    
    def clear(self) -> None:
        """Clear display."""
        self.display_buffer = [[' ' for _ in range(self.cols)] for _ in range(self.rows)]
        self.cursor_pos = (0, 0)
        logger.debug("LCD display cleared")
    
    def cursor_mode(self, cursor: bool = False, blink: bool = False) -> None:
        """Set cursor display mode."""
        self.cursor_visible = cursor
        self.blink_cursor = blink
        logger.debug(f"LCD cursor mode: visible={cursor}, blink={blink}")
    
    def backlight_enabled(self, enabled: bool) -> None:
        """Enable/disable backlight."""
        self.backlight = enabled
        logger.debug(f"LCD backlight: {enabled}")
    
    def get_display_content(self) -> List[str]:
        """Get current display content as list of strings."""
        return [''.join(row) for row in self.display_buffer]
    
    def get_display_state(self) -> Dict[str, Any]:
        """Get current display state (for testing)."""
        return {
            'address': self.address,
            'cols': self.cols,
            'rows': self.rows,
            'content': self.get_display_content(),
            'cursor_pos': self.cursor_pos,
            'cursor_visible': self.cursor_visible,
            'blink_cursor': self.blink_cursor,
            'backlight': self.backlight
        }

# =============================================================================
# Hardware Test Utilities
# =============================================================================

class HardwareTestHarness:
    """Test harness for coordinating hardware simulation."""
    
    def __init__(self):
        self.gpio = MockRPiGPIO()
        self.i2c_buses: Dict[int, MockSMBus] = {}
        self.temperature_sensors: Dict[str, MockTemperatureSensor] = {}
        self.displays_7seg: Dict[int, Mock7SegmentDisplay] = {}
        self.displays_lcd: Dict[int, MockLCDisplay] = {}
        
        logger.debug("HardwareTestHarness initialized")
    
    def get_i2c_bus(self, bus_id: int = 1) -> MockSMBus:
        """Get or create I2C bus."""
        if bus_id not in self.i2c_buses:
            self.i2c_buses[bus_id] = MockSMBus(bus_id)
        return self.i2c_buses[bus_id]
    
    def add_temperature_sensor(self, sensor_id: str, base_temp: float = 20.0) -> MockTemperatureSensor:
        """Add temperature sensor."""
        sensor = MockTemperatureSensor(base_temp)
        self.temperature_sensors[sensor_id] = sensor
        return sensor
    
    def add_7seg_display(self, address: int = 0x70) -> Mock7SegmentDisplay:
        """Add 7-segment display."""
        display = Mock7SegmentDisplay(address)
        self.displays_7seg[address] = display
        return display
    
    def add_lcd_display(self, address: int = 0x27, cols: int = 20, rows: int = 4) -> MockLCDisplay:
        """Add LCD display."""
        display = MockLCDisplay(address, cols, rows)
        self.displays_lcd[address] = display
        return display
    
    def simulate_brewing_process(self, duration: int = 60) -> None:
        """Simulate a brewing process with temperature changes."""
        logger.info(f"Starting brewing process simulation ({duration}s)")
        
        # Simulate mash temperature profile
        if 'mash_temp' in self.temperature_sensors:
            mash_sensor = self.temperature_sensors['mash_temp']
            
            # Heat up to mash temperature
            mash_sensor.set_target_temperature(65.0)
            
            # After half duration, cool down
            def cooldown():
                time.sleep(duration / 2)
                mash_sensor.set_target_temperature(20.0)
            
            threading.Thread(target=cooldown, daemon=True).start()
    
    def get_system_state(self) -> Dict[str, Any]:
        """Get complete hardware system state."""
        return {
            'gpio_pins': {pin: state.__dict__ for pin, state in self.gpio._pins.items()},
            'i2c_devices': {
                bus_id: {addr: device.__dict__ for addr, device in bus._devices.items()}
                for bus_id, bus in self.i2c_buses.items()
            },
            'temperature_sensors': {
                sensor_id: {
                    'current_temp': sensor.current_temperature,
                    'target_temp': sensor._target_temperature,
                    'readings_count': len(sensor._readings_history)
                }
                for sensor_id, sensor in self.temperature_sensors.items()
            },
            '7seg_displays': {addr: display.get_display_state() for addr, display in self.displays_7seg.items()},
            'lcd_displays': {addr: display.get_display_state() for addr, display in self.displays_lcd.items()}
        }
    
    def reset_all(self) -> None:
        """Reset all hardware to initial state."""
        self.gpio.cleanup()
        for bus in self.i2c_buses.values():
            bus.close()
        for sensor in self.temperature_sensors.values():
            sensor.reset_sensor()
        
        logger.info("All hardware reset to initial state")

# =============================================================================
# Factory Functions
# =============================================================================

def create_hardware_test_harness() -> HardwareTestHarness:
    """Create a configured hardware test harness."""
    return HardwareTestHarness()

def create_brewmotron_hardware_setup() -> HardwareTestHarness:
    """Create hardware setup specifically for Brewmotron testing."""
    harness = HardwareTestHarness()
    
    # Add typical Brewmotron hardware
    harness.add_temperature_sensor('mash_temp', 20.0)
    harness.add_temperature_sensor('boil_temp', 20.0)
    harness.add_temperature_sensor('ferment_temp', 20.0)
    
    # Add 7-segment displays
    for addr in range(0x70, 0x76):
        harness.add_7seg_display(addr)
    
    # Add LCD display
    harness.add_lcd_display(0x27, 20, 4)
    
    logger.info("Brewmotron hardware setup created")
    return harness

# Import math for temperature simulation
import math