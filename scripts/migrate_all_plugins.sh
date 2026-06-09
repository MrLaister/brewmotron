#!/bin/bash
# Plugin Directory Migration Script
# Migrates all plugins from hyphenated names to underscore names

set -e

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SRC_DIR"

echo "========================================================================"
echo "Plugin Directory Migration"
echo "Source Directory: $SRC_DIR"
echo "========================================================================"

# Function to migrate a single plugin
migrate_plugin() {
    local old_name="$1"
    local new_name="$2"

    echo ""
    echo "Migrating: $old_name -> $new_name"

    if [ ! -d "$old_name" ]; then
        echo "  WARNING: Plugin directory not found: $old_name"
        return 1
    fi

    if [ -d "$new_name" ]; then
        echo "  INFO: Target directory already exists: $new_name (skipping)"
        return 0
    fi

    # Create new directory
    mkdir -p "$new_name"

    # Check for double-nested structure
    if [ -d "$old_name/$old_name" ]; then
        echo "  Flattening double-nested structure..."

        # Copy files from inner directory to new top level
        cp -r "$old_name/$old_name"/* "$new_name/"

        # Copy other files from outer directory (excluding inner directory)
        find "$old_name" -maxdepth 1 -type f -exec cp {} "$new_name/" \;
    else
        # Simple copy
        cp -r "$old_name"/* "$new_name/"
    fi

    echo "  Created: $new_name"
    return 0
}

# Migrate all plugins
migrate_plugin "cbpi4-7SegDisplay" "cbpi4_7seg_display"
migrate_plugin "cbpi4-AlwaysONGPIO" "cbpi4_always_on_gpio"
migrate_plugin "cbpi4-BMT-Key" "cbpi4_bmt_key"
migrate_plugin "cbpi4-BMT-MomentaryButtons" "cbpi4_bmt_momentary_buttons"
migrate_plugin "cbpi4-GPIOInput" "cbpi4_gpio_input"
migrate_plugin "cbpi4-i2cTempSensor" "cbpi4_i2c_temp_sensor"
migrate_plugin "cbpi4-InternetConnectedGPIO" "cbpi4_internet_connected_gpio"
migrate_plugin "cbpi4-LCDisplay" "cbpi4_lcd_display"
migrate_plugin "cbpi4-NOR3" "cbpi4_nor3"
migrate_plugin "cbpi4-OneAtATime" "cbpi4_one_at_a_time"
migrate_plugin "cbpi4-ZigbeeGPIO" "cbpi4_zigbee_gpio"

echo ""
echo "========================================================================"
echo "Migration Complete!"
echo "========================================================================"
echo ""
echo "Next steps:"
echo "1. Update setup.py files in each plugin"
echo "2. Remove old directories after verification"
echo "3. Update GitHub Actions coverage configuration"
echo "4. Update documentation"
