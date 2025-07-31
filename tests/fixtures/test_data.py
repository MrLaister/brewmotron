"""
Test Data Fixtures and Factories

Provides realistic test data for Brewmotron plugin testing, including
configurations, sensor readings, brewing recipes, and hardware states.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from factory import Factory, Faker, SubFactory, LazyAttribute, Sequence
from factory.fuzzy import FuzzyChoice, FuzzyFloat, FuzzyInteger, FuzzyDateTime
import factory

# =============================================================================
# Data Classes for Test Data
# =============================================================================

@dataclass
class PluginConfig:
    """Plugin configuration data."""
    id: str
    name: str
    type: str  # 'Actor', 'Sensor', 'Extension'
    active: bool = True
    props: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SensorReading:
    """Sensor reading data."""
    sensor_id: str
    value: float
    unit: str
    timestamp: datetime
    quality: float = 1.0

@dataclass
class ActorState:
    """Actor state data."""
    actor_id: str
    state: bool
    timestamp: datetime
    power: int = 0

@dataclass
class BrewingRecipe:
    """Brewing recipe data."""
    id: str
    name: str
    style: str
    batch_size: float  # liters
    mash_schedule: List[Dict[str, Any]]
    hop_schedule: List[Dict[str, Any]]
    fermentation_schedule: List[Dict[str, Any]]

@dataclass
class I2CDeviceConfig:
    """I2C device configuration."""
    address: int
    device_type: str
    registers: Dict[int, int] = field(default_factory=dict)

@dataclass
class GPIOPinConfig:
    """GPIO pin configuration."""
    pin: int
    mode: str  # 'IN', 'OUT'
    initial_state: int = 0
    pull_up_down: str = 'OFF'

# =============================================================================
# Factory Classes
# =============================================================================

class PluginConfigFactory(Factory):
    """Factory for plugin configurations."""
    
    class Meta:
        model = PluginConfig
    
    id = Sequence(lambda n: f"plugin_{n}")
    name = Faker('word')
    type = FuzzyChoice(['Actor', 'Sensor', 'Extension'])
    active = True
    props = LazyAttribute(lambda obj: {
        'GPIO': random.randint(1, 27) if obj.type == 'Actor' else None,
        'Inverted': random.choice(['Yes', 'No']),
        'I2C_Address': f"0x{random.randint(0x20, 0x77):02X}" if obj.type == 'Sensor' else None
    })

class GPIOActorConfigFactory(PluginConfigFactory):
    """Factory for GPIO actor configurations."""
    
    type = 'Actor'
    props = LazyAttribute(lambda obj: {
        'GPIO': random.randint(1, 27),
        'Inverted': random.choice(['Yes', 'No']),
        'LinkedActor': None
    })

class ExtensionConfigFactory(PluginConfigFactory):
    """Factory for Extension plugin configurations."""
    
    type = 'Extension'
    props = LazyAttribute(lambda obj: {})

class I2CSensorConfigFactory(PluginConfigFactory):
    """Factory for I2C sensor configurations."""
    
    type = 'Sensor'
    props = LazyAttribute(lambda obj: {
        'I2C_Address': f"0x{random.randint(0x48, 0x4F):02X}",
        'Sensor_Type': random.choice(['DS18B20', 'ADS1115', 'BME280']),
        'Offset': round(random.uniform(-2.0, 2.0), 2),
        'Interval': random.randint(1, 10)
    })

class SensorReadingFactory(Factory):
    """Factory for sensor readings."""
    
    class Meta:
        model = SensorReading
    
    sensor_id = Sequence(lambda n: f"sensor_{n}")
    value = FuzzyFloat(-10.0, 100.0)
    unit = FuzzyChoice(['C', 'F', 'V', 'A', '%'])
    timestamp = FuzzyDateTime(datetime.now(timezone.utc) - timedelta(hours=1))
    quality = FuzzyFloat(0.8, 1.0)

class TemperatureSensorReadingFactory(SensorReadingFactory):
    """Factory for temperature sensor readings."""
    
    value = FuzzyFloat(15.0, 25.0)  # Room temperature range
    unit = 'C'

class MashTemperatureReadingFactory(SensorReadingFactory):
    """Factory for mash temperature readings."""
    
    value = FuzzyFloat(60.0, 70.0)  # Typical mash temperature range
    unit = 'C'

class BoilTemperatureReadingFactory(SensorReadingFactory):
    """Factory for boil temperature readings."""
    
    value = FuzzyFloat(95.0, 105.0)  # Near boiling range
    unit = 'C'

class ActorStateFactory(Factory):
    """Factory for actor states."""
    
    class Meta:
        model = ActorState
    
    actor_id = Sequence(lambda n: f"actor_{n}")
    state = FuzzyChoice([True, False])
    power = FuzzyInteger(0, 100)
    timestamp = FuzzyDateTime(datetime.now(timezone.utc) - timedelta(minutes=30))

class BrewingRecipeFactory(Factory):
    """Factory for brewing recipes."""
    
    class Meta:
        model = BrewingRecipe
    
    id = LazyAttribute(lambda obj: str(uuid.uuid4()))
    name = Faker('sentence', nb_words=3)
    style = FuzzyChoice([
        'American IPA', 'German Wheat', 'English Bitter', 'Belgian Tripel',
        'Russian Imperial Stout', 'Czech Pilsner', 'American Porter'
    ])
    batch_size = FuzzyFloat(10.0, 50.0)
    
    mash_schedule = LazyAttribute(lambda obj: [
        {'temperature': 65.0, 'time': 60, 'description': 'Saccharification Rest'},
        {'temperature': 72.0, 'time': 15, 'description': 'Mashout'}
    ])
    
    hop_schedule = LazyAttribute(lambda obj: [
        {'time': 60, 'amount': '20g', 'variety': 'Chinook', 'alpha_acid': 13.0, 'type': 'bittering'},
        {'time': 20, 'amount': '15g', 'variety': 'Cascade', 'alpha_acid': 7.0, 'type': 'flavor'},
        {'time': 5, 'amount': '10g', 'variety': 'Centennial', 'alpha_acid': 10.0, 'type': 'aroma'}
    ])
    
    fermentation_schedule = LazyAttribute(lambda obj: [
        {'temperature': 18.0, 'time': 7, 'description': 'Primary Fermentation'},
        {'temperature': 20.0, 'time': 3, 'description': 'Secondary Fermentation'}
    ])

class I2CDeviceConfigFactory(Factory):
    """Factory for I2C device configurations."""
    
    class Meta:
        model = I2CDeviceConfig
    
    address = FuzzyInteger(0x20, 0x77)
    device_type = FuzzyChoice(['HT16K33', 'ADS1115', 'PCF8574', 'BME280'])
    registers = LazyAttribute(lambda obj: {
        0x00: random.randint(0, 255),
        0x01: random.randint(0, 255),
        0x02: random.randint(0, 255)
    })

class SevenSegmentDisplayConfigFactory(I2CDeviceConfigFactory):
    """Factory for 7-segment display configurations."""
    
    address = FuzzyInteger(0x70, 0x77)
    device_type = 'HT16K33'
    registers = LazyAttribute(lambda obj: {
        0x21: 0x01,  # System setup
        0xEF: 0x00,  # Display setup
        0x81: random.randint(0, 15),  # Brightness
    })

class GPIOPinConfigFactory(Factory):
    """Factory for GPIO pin configurations."""
    
    class Meta:
        model = GPIOPinConfig
    
    pin = FuzzyInteger(1, 27)
    mode = FuzzyChoice(['IN', 'OUT'])
    initial_state = FuzzyChoice([0, 1])
    pull_up_down = FuzzyChoice(['OFF', 'UP', 'DOWN'])

# =============================================================================
# Predefined Test Data Sets
# =============================================================================

class BrewmotronTestData:
    """Predefined test data sets for Brewmotron testing."""
    
    @staticmethod
    def get_standard_plugin_configs() -> List[PluginConfig]:
        """Get standard Brewmotron plugin configurations."""
        return [
            PluginConfig(
                id="7seg_display",
                name="7SegDisplay",
                type="Extension",
                props={
                    "I2C_Bus": 1,
                    "Addresses": [0x70, 0x71, 0x72],
                    "Brightness": 8,
                    "Update_Interval": 1
                }
            ),
            PluginConfig(
                id="lcd_display",
                name="LCDisplay",
                type="Extension",
                props={
                    "I2C_Address": "0x27",
                    "Cols": 20,
                    "Rows": 4,
                    "Backlight": True
                }
            ),
            PluginConfig(
                id="mash_temp_sensor",
                name="i2cTempSensor",
                type="Sensor",
                props={
                    "I2C_Address": "0x48",
                    "Channel": 0,
                    "Offset": 0.0,
                    "Interval": 2
                }
            ),
            PluginConfig(
                id="pump_gpio",
                name="GPIOInput",
                type="Actor",
                props={
                    "GPIO": 18,
                    "Inverted": "No",
                    "LinkedActor": None
                }
            ),
            PluginConfig(
                id="heating_element",
                name="AlwaysONGPIO",
                type="Actor",
                props={
                    "GPIO": 19,
                    "Inverted": "No"
                }
            ),
            PluginConfig(
                id="mode_key",
                name="BMT-Key",
                type="Extension",
                props={
                    "Key_File": "/home/brewmotron/mode.key",
                    "Default_Mode": "brew"
                }
            ),
            PluginConfig(
                id="momentary_buttons",
                name="BMT-MomentaryButtons",
                type="Actor",
                props={
                    "GPIO": 21,
                    "Inverted": "No",
                    "Bounce_Time": 200
                }
            ),
            PluginConfig(
                id="internet_gpio",
                name="InternetConnectedGPIO",
                type="Actor",
                props={
                    "GPIO": 22,
                    "Inverted": "No",
                    "Check_Host": "google.com",
                    "Check_Port": 80
                }
            ),
            PluginConfig(
                id="one_at_a_time",
                name="OneAtATime",
                type="Actor",
                props={
                    "actor": None,
                    "OneAtATime group": 1
                }
            ),
            PluginConfig(
                id="nor3_logic",
                name="NOR3",
                type="Actor",
                props={
                    "actor": None
                }
            )
        ]
    
    @staticmethod
    def get_brewing_temperature_profile() -> List[SensorReading]:
        """Get a realistic brewing temperature profile."""
        readings = []
        base_time = datetime.now() - timedelta(hours=6)
        
        # Heating phase (0-60 minutes)
        for i in range(60):
            temp = 20.0 + (45.0 * i / 60.0)  # Heat from 20°C to 65°C
            readings.append(SensorReading(
                sensor_id="mash_temp",
                value=temp + random.gauss(0, 0.2),  # Add some noise
                unit="C",
                timestamp=base_time + timedelta(minutes=i),
                quality=0.95 + random.uniform(-0.05, 0.05)
            ))
        
        # Mash phase (60-120 minutes) - stable temperature
        for i in range(60, 120):
            temp = 65.0 + random.gauss(0, 0.5)  # Stable with small variations
            readings.append(SensorReading(
                sensor_id="mash_temp",
                value=temp,
                unit="C",
                timestamp=base_time + timedelta(minutes=i),
                quality=0.98
            ))
        
        # Boil phase (120-180 minutes) - heat to boiling
        for i in range(120, 180):
            temp = 65.0 + (35.0 * (i - 120) / 60.0)  # Heat from 65°C to 100°C
            readings.append(SensorReading(
                sensor_id="mash_temp",
                value=temp + random.gauss(0, 0.3),
                unit="C",
                timestamp=base_time + timedelta(minutes=i),
                quality=0.97
            ))
        
        # Boiling phase (180-240 minutes) - stable boiling
        for i in range(180, 240):
            temp = 100.0 + random.gauss(0, 1.0)  # Stable boiling
            readings.append(SensorReading(
                sensor_id="mash_temp",
                value=temp,
                unit="C",
                timestamp=base_time + timedelta(minutes=i),
                quality=0.99
            ))
        
        return readings
    
    @staticmethod
    def get_i2c_device_states() -> Dict[int, I2CDeviceConfig]:
        """Get typical I2C device states for Brewmotron."""
        devices = {}
        
        # 7-segment displays (0x70-0x75)
        for addr in range(0x70, 0x76):
            devices[addr] = I2CDeviceConfig(
                address=addr,
                device_type="HT16K33",
                registers={
                    0x21: 0x01,  # System setup
                    0xEF: 0x00,  # Display setup
                    0x81: 8,     # Brightness
                    0x00: 0x00,  # Display data
                    0x02: 0x00,
                    0x04: 0x00,
                    0x06: 0x00,
                    0x08: 0x00
                }
            )
        
        # ADS1115 ADC (0x48)
        devices[0x48] = I2CDeviceConfig(
            address=0x48,
            device_type="ADS1115",
            registers={
                0x00: 0x8000,  # Conversion register
                0x01: 0x0583,  # Config register
                0x02: 0x8000,  # Lo_thresh register
                0x03: 0x7FFF   # Hi_thresh register
            }
        )
        
        # LCD controller (0x27)
        devices[0x27] = I2CDeviceConfig(
            address=0x27,
            device_type="PCF8574",
            registers={
                0x00: 0xFF  # All pins high initially
            }
        )
        
        return devices
    
    @staticmethod
    def get_gpio_pin_configs() -> List[GPIOPinConfig]:
        """Get typical GPIO pin configurations for Brewmotron."""
        return [
            GPIOPinConfig(pin=18, mode='OUT', initial_state=0),  # Pump
            GPIOPinConfig(pin=19, mode='OUT', initial_state=0),  # Heating element
            GPIOPinConfig(pin=20, mode='OUT', initial_state=0),  # Valve 1
            GPIOPinConfig(pin=21, mode='IN', pull_up_down='UP'),  # Button 1
            GPIOPinConfig(pin=22, mode='OUT', initial_state=0),  # Internet GPIO
            GPIOPinConfig(pin=23, mode='IN', pull_up_down='UP'),  # Button 2
            GPIOPinConfig(pin=24, mode='OUT', initial_state=0),  # Valve 2
            GPIOPinConfig(pin=25, mode='OUT', initial_state=0),  # LED indicator
        ]
    
    @staticmethod
    def get_sample_brewing_recipe() -> BrewingRecipe:
        """Get a sample brewing recipe."""
        return BrewingRecipe(
            id=str(uuid.uuid4()),
            name="Brewmotron Test IPA",
            style="American IPA",
            batch_size=20.0,
            mash_schedule=[
                {
                    'step': 'Protein Rest',
                    'temperature': 50.0,
                    'time': 15,
                    'description': 'Protein breakdown'
                },
                {
                    'step': 'Saccharification Rest',
                    'temperature': 65.0,
                    'time': 60,
                    'description': 'Convert starches to sugars'
                },
                {
                    'step': 'Mashout',
                    'temperature': 75.0,
                    'time': 10,
                    'description': 'Stop enzyme activity'
                }
            ],
            hop_schedule=[
                {
                    'time': 60,
                    'amount': '25g',
                    'variety': 'Magnum',
                    'alpha_acid': 14.0,
                    'type': 'bittering',
                    'form': 'pellet'
                },
                {
                    'time': 20,
                    'amount': '20g',
                    'variety': 'Cascade',
                    'alpha_acid': 7.0,
                    'type': 'flavor',
                    'form': 'pellet'
                },
                {
                    'time': 5,
                    'amount': '15g',
                    'variety': 'Centennial',
                    'alpha_acid': 10.0,
                    'type': 'aroma',
                    'form': 'pellet'
                },
                {
                    'time': 0,
                    'amount': '10g',
                    'variety': 'Citra',
                    'alpha_acid': 12.0,
                    'type': 'aroma',
                    'form': 'pellet'
                }
            ],
            fermentation_schedule=[
                {
                    'stage': 'Primary',
                    'temperature': 18.0,
                    'time': 7,
                    'description': 'Primary fermentation'
                },
                {
                    'stage': 'Secondary',
                    'temperature': 19.0,
                    'time': 5,
                    'description': 'Secondary fermentation and conditioning'
                },
                {
                    'stage': 'Cold Crash',
                    'temperature': 2.0,
                    'time': 2,
                    'description': 'Cold crash for clarity'
                }
            ]
        )

# =============================================================================
# Test Data Generators
# =============================================================================

def generate_sensor_readings(sensor_id: str, count: int = 100, 
                           base_value: float = 20.0, 
                           variation: float = 2.0) -> List[SensorReading]:
    """Generate a series of sensor readings with realistic variation."""
    readings = []
    current_time = datetime.now() - timedelta(minutes=count)
    
    for i in range(count):
        # Add some trending and noise
        trend = (i / count) * variation  # Gradual change over time
        noise = random.gauss(0, variation * 0.1)  # Small random variations
        
        value = base_value + trend + noise
        
        readings.append(SensorReading(
            sensor_id=sensor_id,
            value=value,
            unit="C",
            timestamp=current_time + timedelta(minutes=i),
            quality=0.95 + random.uniform(-0.05, 0.05)
        ))
    
    return readings

def generate_actor_state_history(actor_id: str, duration_minutes: int = 120) -> List[ActorState]:
    """Generate actor state change history."""
    states = []
    current_time = datetime.now() - timedelta(minutes=duration_minutes)
    current_state = False
    
    # Generate state changes at random intervals
    while current_time < datetime.now():
        states.append(ActorState(
            actor_id=actor_id,
            state=current_state,
            power=random.randint(0, 100) if current_state else 0,
            timestamp=current_time
        ))
        
        # Random interval between 5-30 minutes
        interval = random.randint(5, 30)
        current_time += timedelta(minutes=interval)
        current_state = not current_state  # Toggle state
    
    return states

def generate_brewing_session_data() -> Dict[str, Any]:
    """Generate complete brewing session data."""
    session_id = str(uuid.uuid4())
    start_time = datetime.now() - timedelta(hours=8)
    
    return {
        'session_id': session_id,
        'start_time': start_time,
        'recipe': BrewmotronTestData.get_sample_brewing_recipe(),
        'temperature_readings': generate_sensor_readings(
            'mash_temp', 480, 20.0, 45.0  # 8 hours of readings
        ),
        'actor_states': {
            'pump': generate_actor_state_history('pump', 480),
            'heater': generate_actor_state_history('heater', 480),
            'valve': generate_actor_state_history('valve', 480)
        },
        'i2c_device_states': BrewmotronTestData.get_i2c_device_states(),
        'gpio_pin_configs': BrewmotronTestData.get_gpio_pin_configs()
    }

# =============================================================================
# Test Data Validation
# =============================================================================

def validate_plugin_config(config: PluginConfig) -> List[str]:
    """Validate plugin configuration and return list of errors."""
    errors = []
    
    if not config.id:
        errors.append("Plugin ID cannot be empty")
    
    if not config.name:
        errors.append("Plugin name cannot be empty")
    
    if config.type not in ['Actor', 'Sensor', 'Extension']:
        errors.append(f"Invalid plugin type: {config.type}")
    
    if config.type == 'Actor' and 'GPIO' in config.props:
        gpio = config.props['GPIO']
        if not isinstance(gpio, int) or gpio < 1 or gpio > 27:
            errors.append(f"Invalid GPIO pin: {gpio}")
    
    return errors

def validate_sensor_reading(reading: SensorReading) -> List[str]:
    """Validate sensor reading and return list of errors."""
    errors = []
    
    if not reading.sensor_id:
        errors.append("Sensor ID cannot be empty")
    
    if reading.unit == 'C' and (reading.value < -273.15 or reading.value > 200.0):
        errors.append(f"Temperature reading out of reasonable range: {reading.value}°C")
    
    if reading.quality < 0.0 or reading.quality > 1.0:
        errors.append(f"Quality must be between 0.0 and 1.0: {reading.quality}")
    
    return errors

# =============================================================================
# Export Functions
# =============================================================================

__all__ = [
    'PluginConfig', 'SensorReading', 'ActorState', 'BrewingRecipe',
    'I2CDeviceConfig', 'GPIOPinConfig',
    'PluginConfigFactory', 'SensorReadingFactory', 'ActorStateFactory',
    'BrewingRecipeFactory', 'I2CDeviceConfigFactory', 'GPIOPinConfigFactory',
    'BrewmotronTestData',
    'generate_sensor_readings', 'generate_actor_state_history',
    'generate_brewing_session_data',
    'validate_plugin_config', 'validate_sensor_reading'
]