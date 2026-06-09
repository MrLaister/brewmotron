#!/usr/bin/env python3
"""
Plugin Directory Migration Script
==================================

Migrates plugin directories from hyphenated names (cbpi4-PluginName) to
underscore names (cbpi4_plugin_name) following PEP 8 conventions.

This script:
1. Renames plugin directories to use underscores
2. Flattens double-nested directory structure
3. Updates setup.py package references
4. Maintains backwards compatibility with PyPI package names

Usage:
    python scripts/migrate_plugin_names.py [--dry-run]
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


class PluginMigrator:
    """Handles migration of plugin directory structures."""

    # Mapping of old names to new names
    PLUGIN_MAPPINGS = {
        "cbpi4-7SegDisplay": "cbpi4_7seg_display",
        "cbpi4-AlwaysONGPIO": "cbpi4_always_on_gpio",
        "cbpi4-BMT-Key": "cbpi4_bmt_key",
        "cbpi4-BMT-MomentaryButtons": "cbpi4_bmt_momentary_buttons",
        "cbpi4-GPIOInput": "cbpi4_gpio_input",
        "cbpi4-i2cTempSensor": "cbpi4_i2c_temp_sensor",
        "cbpi4-InternetConnectedGPIO": "cbpi4_internet_connected_gpio",
        "cbpi4-LCDisplay": "cbpi4_lcd_display",
        "cbpi4-NOR3": "cbpi4_nor3",
        "cbpi4-OneAtATime": "cbpi4_one_at_a_time",
        "cbpi4-ZigbeeGPIO": "cbpi4_zigbee_gpio",
    }

    def __init__(self, src_dir: Path, dry_run: bool = False):
        self.src_dir = src_dir
        self.dry_run = dry_run
        self.migration_log = []

    def log(self, message: str, level: str = "INFO"):
        """Log migration messages."""
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"{prefix}[{level}] {message}")
        self.migration_log.append(f"{prefix}[{level}] {message}")

    def migrate_plugin(self, old_name: str, new_name: str) -> bool:
        """Migrate a single plugin directory."""
        old_path = self.src_dir / old_name
        new_path = self.src_dir / new_name

        if not old_path.exists():
            self.log(f"Plugin directory not found: {old_path}", "WARNING")
            return False

        if new_path.exists():
            self.log(f"Target directory already exists: {new_path}", "ERROR")
            return False

        self.log(f"Migrating: {old_name} -> {new_name}")

        # Check for double-nested structure
        inner_old_path = old_path / old_name
        has_double_nesting = inner_old_path.exists() and inner_old_path.is_dir()

        if has_double_nesting:
            self.log(f"  Found double-nested structure: {old_name}/{old_name}/")
            if not self.dry_run:
                # Create new directory
                new_path.mkdir(parents=True, exist_ok=True)

                # Move contents from inner directory to new top level
                for item in inner_old_path.iterdir():
                    dest = new_path / item.name
                    self.log(f"  Moving: {item.name} -> {new_name}/{item.name}")
                    shutil.move(str(item), str(dest))

                # Move other files from outer directory (setup.py, README, etc)
                for item in old_path.iterdir():
                    if item.name != old_name:  # Skip the inner directory we just processed
                        dest = new_path / item.name
                        self.log(f"  Moving: {item.name} -> {new_name}/{item.name}")
                        if dest.exists():
                            self.log(f"    Skipping {item.name} (already exists)", "WARNING")
                        else:
                            shutil.move(str(item), str(dest))

                # Remove old directory
                shutil.rmtree(old_path)
                self.log(f"  Removed old directory: {old_path}")
            else:
                self.log(f"  [DRY-RUN] Would flatten {old_name}/{old_name}/ -> {new_name}/")
        else:
            # Simple rename, no flattening needed
            if not self.dry_run:
                shutil.move(str(old_path), str(new_path))
            self.log(f"  Renamed: {old_path} -> {new_path}")

        return True

    def update_setup_py(self, plugin_dir: Path, old_name: str, new_name: str) -> bool:
        """Update setup.py to reference new module name."""
        setup_file = plugin_dir / "setup.py"

        if not setup_file.exists():
            self.log(f"  setup.py not found in {plugin_dir}", "WARNING")
            return False

        self.log(f"  Updating setup.py in {plugin_dir.name}")

        if self.dry_run:
            self.log(f"    [DRY-RUN] Would update packages reference: {old_name} -> {new_name}")
            return True

        # Read setup.py
        content = setup_file.read_text(encoding="utf-8")

        # Update packages parameter
        # Handle both formats: packages=["old-name"] and find_packages()
        if f'packages=["{old_name}"]' in content:
            content = content.replace(
                f'packages=["{old_name}"]',
                f'packages=["{new_name}"]'
            )
            self.log(f"    Updated packages=['{old_name}'] -> packages=['{new_name}']")

        if f'"{old_name}": [' in content:
            content = content.replace(
                f'"{old_name}": [',
                f'"{new_name}": ['
            )
            self.log(f"    Updated package_data key: {old_name} -> {new_name}")

        # Write updated setup.py
        setup_file.write_text(content, encoding="utf-8")
        return True

    def migrate_all(self):
        """Migrate all plugins."""
        self.log("=" * 70)
        self.log("Plugin Directory Migration Starting")
        self.log("=" * 70)

        if self.dry_run:
            self.log("DRY-RUN MODE: No changes will be made", "WARNING")

        success_count = 0
        fail_count = 0

        for old_name, new_name in self.PLUGIN_MAPPINGS.items():
            self.log(f"\n{'=' * 70}")
            if self.migrate_plugin(old_name, new_name):
                # Update setup.py in the newly renamed directory
                if not self.dry_run:
                    self.update_setup_py(self.src_dir / new_name, old_name, new_name)
                success_count += 1
            else:
                fail_count += 1

        self.log(f"\n{'=' * 70}")
        self.log("Migration Summary")
        self.log("=" * 70)
        self.log(f"Successful migrations: {success_count}")
        self.log(f"Failed migrations: {fail_count}")
        self.log(f"Total plugins: {len(self.PLUGIN_MAPPINGS)}")

        return success_count, fail_count


def main():
    parser = argparse.ArgumentParser(
        description="Migrate plugin directories from hyphens to underscores"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Source directory containing plugins (default: auto-detect)"
    )

    args = parser.parse_args()

    # Verify source directory
    if not args.src_dir.exists():
        print(f"ERROR: Source directory not found: {args.src_dir}", file=sys.stderr)
        sys.exit(1)

    # Create migrator and run
    migrator = PluginMigrator(args.src_dir, dry_run=args.dry_run)
    success, fail = migrator.migrate_all()

    # Exit with appropriate code
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
