# Plugin Directory Migration Script (PowerShell)
# Migrates plugin directories from hyphenated names to underscore names

$ErrorActionPreference = "Stop"

# Plugin mappings
$pluginMappings = @{
    "cbpi4-7SegDisplay" = "cbpi4_7seg_display"
    "cbpi4-AlwaysONGPIO" = "cbpi4_always_on_gpio"
    "cbpi4-BMT-Key" = "cbpi4_bmt_key"
    "cbpi4-BMT-MomentaryButtons" = "cbpi4_bmt_momentary_buttons"
    "cbpi4-GPIOInput" = "cbpi4_gpio_input"
    "cbpi4-i2cTempSensor" = "cbpi4_i2c_temp_sensor"
    "cbpi4-InternetConnectedGPIO" = "cbpi4_internet_connected_gpio"
    "cbpi4-LCDisplay" = "cbpi4_lcd_display"
    "cbpi4-NOR3" = "cbpi4_nor3"
    "cbpi4-OneAtATime" = "cbpi4_one_at_a_time"
    "cbpi4-ZigbeeGPIO" = "cbpi4_zigbee_gpio"
}

$srcDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=" * 70
Write-Host "Plugin Directory Migration"
Write-Host "Source Directory: $srcDir"
Write-Host "=" * 70

foreach ($oldName in $pluginMappings.Keys) {
    $newName = $pluginMappings[$oldName]
    $oldPath = Join-Path $srcDir $oldName
    $newPath = Join-Path $srcDir $newName

    Write-Host "`nMigrating: $oldName -> $newName"

    if (-Not (Test-Path $oldPath)) {
        Write-Host "  WARNING: Plugin directory not found: $oldPath" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $newPath) {
        Write-Host "  ERROR: Target directory already exists: $newPath" -ForegroundColor Red
        continue
    }

    # Create new directory
    New-Item -ItemType Directory -Path $newPath | Out-Null

    # Check for double-nested structure
    $innerOldPath = Join-Path $oldPath $oldName
    if (Test-Path $innerOldPath) {
        Write-Host "  Flattening double-nested structure..."

        # Copy files from inner directory to new top level
        Get-ChildItem -Path $innerOldPath | ForEach-Object {
            $dest = Join-Path $newPath $_.Name
            Write-Host "    Moving: $($_.Name)"
            Move-Item -Path $_.FullName -Destination $dest
        }

        # Copy other files from outer directory
        Get-ChildItem -Path $oldPath | Where-Object { $_.Name -ne $oldName } | ForEach-Object {
            $dest = Join-Path $newPath $_.Name
            Write-Host "    Moving: $($_.Name)"
            Move-Item -Path $_.FullName -Destination $dest
        }
    } else {
        # Simple move
        Get-ChildItem -Path $oldPath | ForEach-Object {
            Move-Item -Path $_.FullName -Destination $newPath
        }
    }

    # Remove old directory
    Remove-Item -Path $oldPath -Recurse -Force
    Write-Host "  Completed: $oldName -> $newName" -ForegroundColor Green
}

Write-Host "`n" + ("=" * 70)
Write-Host "Migration Complete!" -ForegroundColor Green
Write-Host "=" * 70
