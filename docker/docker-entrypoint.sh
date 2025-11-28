#!/bin/bash
set -e

echo "========================================="
echo "Brewmotron Manual Test Environment"
echo "========================================="

# Initialize cbpi config if it doesn't exist
if [ ! -f "${CBPI_CONFIG_FOLDER}/config.yaml" ]; then
    echo "Initializing CraftBeerPi4 configuration..."
    cbpi setup
fi

# Install Brewmotron plugins if requested
if [ "${INSTALL_PLUGINS}" = "true" ]; then
    echo "Installing Brewmotron plugins..."

    # List of plugin directories in src/
    PLUGINS=(
        "cbpi4-7SegDisplay"
        "cbpi4-AlwaysONGPIO"
        "cbpi4-BMT-Key"
        "cbpi4-BMT-MomentaryButtons"
        "cbpi4-GPIOInput"
        "cbpi4-InternetConnectedGPIO"
        "cbpi4-LCDisplay"
        "cbpi4-NOR3"
        "cbpi4-OneAtATime"
        "cbpi4-i2cTempSensor"
    )

    for plugin in "${PLUGINS[@]}"; do
        if [ -d "/brewmotron/${plugin}" ]; then
            echo "Installing ${plugin}..."
            cd "/brewmotron/${plugin}"

            # Convert plugin name: cbpi4-7SegDisplay -> cbpi4_7segdisplay
            PLUGIN_MODULE=$(echo "${plugin}" | tr '[:upper:]' '[:lower:]' | tr '-' '_')

            # Fix package directory structure - rename dash directory to underscore
            if [ -d "${plugin}" ]; then
                echo "  Renaming package directory: ${plugin} -> ${PLUGIN_MODULE}"
                mv "${plugin}" "${PLUGIN_MODULE}"
            elif [ ! -d "${PLUGIN_MODULE}" ]; then
                echo "  Warning: No package directory found for ${plugin}"
            fi

            # Update setup.py to reference correct package name
            if [ -f "setup.py" ]; then
                echo "  Updating setup.py package references..."
                python3 << EOF
import re

plugin_name = "${plugin}"
plugin_module = "${PLUGIN_MODULE}"

with open('setup.py', 'r') as f:
    content = f.read()

# Replace find_packages() to explicitly list the renamed package
content = re.sub(
    r'packages=find_packages\(\)',
    f"packages=['{plugin_module}']",
    content
)

# Also replace any hardcoded package lists - use Python variable not bash
content = re.sub(
    rf"packages=\[.*?'{re.escape(plugin_name)}'.*?\]",
    f"packages=['{plugin_module}']",
    content
)

# Fix package_data keys - replace dash versions with underscore versions
content = re.sub(
    rf'"{re.escape(plugin_name)}":\s*\[',
    f'"{plugin_module}": [',
    content
)
content = re.sub(
    rf"'{re.escape(plugin_name)}':\s*\[",
    f"'{plugin_module}': [",
    content
)

# Add entry_points if missing
if 'entry_points' not in content:
    pattern = r'(install_requires=\[.*?\],)'
    entry_point = f'    entry_points={{\n        "cbpi.extension": ["{plugin_name} = {plugin_module}"]\n    }},'
    replacement = r'\1\n' + entry_point
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    print("  ✓ Entry points added")

with open('setup.py', 'w') as f:
    f.write(content)
print("  ✓ setup.py updated")
EOF
            fi

            # Install plugin
            pipx runpip cbpi4 install -e .
            echo "✓ ${plugin} installed"
        else
            echo "Warning: Plugin directory ${plugin} not found"
        fi
    done

    cd /brewmotron
    echo "Plugin installation complete!"
fi

echo "========================================="
echo "Starting CraftBeerPi4..."
echo "Web interface will be available at:"
echo "  http://localhost:8000"
echo "========================================="

# Execute the main command
exec "$@"
