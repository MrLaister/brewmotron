# Plugin Directory Structure Migration

**Date**: November 30, 2024
**Type**: Breaking Change (Internal Only)
**Status**: ✅ Completed

## Summary

Migrated all CraftBeerPi4 plugin directories from hyphenated names (incompatible with Python module naming) to underscore names following PEP 8 conventions.

## Changes Made

### 1. Directory Renaming

All plugin directories were renamed to use underscores instead of hyphens and converted to lowercase:

| Old Name (Hyphenated) | New Name (Underscores) |
|-----------------------|------------------------|
| `cbpi4-7SegDisplay` | `cbpi4_7seg_display` |
| `cbpi4-AlwaysONGPIO` | `cbpi4_always_on_gpio` |
| `cbpi4-BMT-Key` | `cbpi4_bmt_key` |
| `cbpi4-BMT-MomentaryButtons` | `cbpi4_bmt_momentary_buttons` |
| `cbpi4-GPIOInput` | `cbpi4_gpio_input` |
| `cbpi4-i2cTempSensor` | `cbpi4_i2c_temp_sensor` |
| `cbpi4-InternetConnectedGPIO` | `cbpi4_internet_connected_gpio` |
| `cbpi4-LCDisplay` | `cbpi4_lcd_display` |
| `cbpi4-NOR3` | `cbpi4_nor3` |
| `cbpi4-OneAtATime` | `cbpi4_one_at_a_time` |

### 2. Directory Structure Flattening

**Old Structure** (double-nested):
```
cbpi4-7SegDisplay/
    cbpi4-7SegDisplay/    ← Inner directory (same name)
        __init__.py
        config.yaml
        static/
    setup.py
    README.md
    LICENSE
```

**New Structure** (flattened):
```
cbpi4_7seg_display/
    __init__.py
    config.yaml
    static/
    setup.py
    README.md
    LICENSE
```

### 3. setup.py Updates

Each plugin's `setup.py` was updated to reference the new module name:

**Before**:
```python
setup(
    name="cbpi4-7SegDisplay",  # PyPI package name (kept for compatibility)
    packages=["cbpi4-7SegDisplay"],  # ❌ Invalid Python module name
)
```

**After**:
```python
setup(
    name="cbpi4-7SegDisplay",  # PyPI package name (unchanged)
    packages=["cbpi4_7seg_display"],  # ✅ Valid Python module name
)
```

### 4. Test Configuration Updates

- **`tests/conftest.py`**: Updated `PLUGIN_DIRS` list with new directory names
- **`tests/real_plugin/conftest.py`**: Updated `get_plugin_path()` and `load_plugin_class()` functions to work with new naming convention

### 5. GitHub Actions

No changes needed - current configuration only measures coverage for `brewmotron_cache_handler` (Phase 1).

## Benefits

1. **✅ Python-compliant module names**: Can now use `import cbpi4_7seg_display` directly
2. **✅ PEP 8 compliance**: Follows Python naming conventions
3. **✅ Simpler structure**: Removed unnecessary double-nesting
4. **✅ Better testability**: Enables proper coverage measurement for plugins
5. **✅ Future-proof**: Allows direct imports in development and testing

## Backwards Compatibility

- **PyPI package names**: Unchanged (still use hyphens like `cbpi4-7SegDisplay`)
- **CraftBeerPi4 compatibility**: Maintained (loads plugins dynamically by package name)
- **Installation**: No changes required for end users

## Impact Assessment

- ✅ **Low Risk**: CraftBeerPi4 loads plugins dynamically, not affected by directory names
- ✅ **Test Suite**: Updated and verified
- ✅ **Documentation**: Updated to reflect new structure
- ✅ **Git History**: Old directories removed, new ones tracked

## Files Modified

1. **Migrated Directories**: 10 plugin directories renamed and flattened
2. **setup.py**: 10 files updated with new module names
3. **tests/conftest.py**: Updated PLUGIN_DIRS list
4. **tests/real_plugin/conftest.py**: Updated path resolution functions
5. **Documentation**: CLAUDE.md, README.md

## Migration Scripts Created

- `scripts/migrate_plugin_names.py` - Python migration script (Windows compatible)
- `scripts/migrate_plugins.ps1` - PowerShell migration script
- `scripts/migrate_all_plugins.sh` - Bash migration script (Git Bash compatible)

## Next Steps

1. ✅ Verify tests pass with new structure
2. ✅ Update documentation
3. 📋 Phase 2: Gradually add plugin coverage in GitHub Actions
4. 📋 Phase 2: Re-enable plugin unit tests after cache handler integration

## Related Issues

- Fixes Python module import limitations
- Addresses GitHub Actions coverage configuration issues (November 16, 2025 fix)
- Aligns with `brewmotron_cache_handler` naming pattern

## Notes

- This is an **internal structure change** only
- **No impact** on plugin functionality or end-user experience
- **No changes** required for existing installations
- Prepares codebase for Phase 2 cache handler integration
