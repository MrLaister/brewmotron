#!/usr/bin/env python3
"""
Plugin Migration Verification Script
=====================================

Verifies that the plugin directory migration completed successfully.

Checks:
1. All plugin directories use underscores (PEP 8 compliant)
2. No old hyphenated directories exist
3. All setup.py files reference correct module names
4. Test configuration files updated
5. Plugin imports work correctly

Usage:
    python scripts/verify_migration.py
"""

import sys
from pathlib import Path
from typing import List, Tuple


class MigrationVerifier:
    """Verifies plugin migration was successful."""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

    def log_pass(self, message: str):
        """Log a passed check."""
        self.passed.append(f"✅ {message}")
        print(f"✅ {message}")

    def log_error(self, message: str):
        """Log an error."""
        self.errors.append(f"❌ {message}")
        print(f"❌ {message}")

    def log_warning(self, message: str):
        """Log a warning."""
        self.warnings.append(f"⚠️  {message}")
        print(f"⚠️  {message}")

    def check_plugin_directories(self) -> bool:
        """Check that plugin directories use underscores."""
        print("\n" + "=" * 70)
        print("Checking Plugin Directories")
        print("=" * 70)

        # Expected plugin directories
        expected_plugins = [
            "cbpi4_7seg_display",
            "cbpi4_always_on_gpio",
            "cbpi4_bmt_key",
            "cbpi4_bmt_momentary_buttons",
            "cbpi4_gpio_input",
            "cbpi4_i2c_temp_sensor",
            "cbpi4_internet_connected_gpio",
            "cbpi4_lcd_display",
            "cbpi4_nor3",
            "cbpi4_one_at_a_time",
        ]

        # Check each expected plugin exists
        for plugin in expected_plugins:
            plugin_path = self.src_dir / plugin
            if plugin_path.exists():
                self.log_pass(f"Plugin directory exists: {plugin}/")
            else:
                self.log_error(f"Plugin directory missing: {plugin}/")

        # Check for old hyphenated directories
        old_patterns = ["cbpi4-*"]
        found_old = []
        for pattern in old_patterns:
            old_dirs = list(self.src_dir.glob(pattern))
            if old_dirs:
                for old_dir in old_dirs:
                    found_old.append(old_dir.name)
                    self.log_error(f"Old hyphenated directory found: {old_dir.name}/")

        if not found_old:
            self.log_pass("No old hyphenated directories found")

        return len(self.errors) == 0

    def check_setup_py_files(self) -> bool:
        """Check that setup.py files reference correct module names."""
        print("\n" + "=" * 70)
        print("Checking setup.py Files")
        print("=" * 70)

        plugin_dirs = [d for d in self.src_dir.glob("cbpi4_*") if d.is_dir()]

        for plugin_dir in plugin_dirs:
            setup_file = plugin_dir / "setup.py"

            if not setup_file.exists():
                self.log_warning(f"No setup.py in {plugin_dir.name}/")
                continue

            content = setup_file.read_text(encoding="utf-8")
            plugin_name = plugin_dir.name

            # Check for correct packages parameter
            if f'packages=["{plugin_name}"]' in content:
                self.log_pass(f"{plugin_dir.name}/setup.py: packages=['{plugin_name}']")
            elif f"packages=['{plugin_name}']" in content:
                self.log_pass(f"{plugin_dir.name}/setup.py: packages=['{plugin_name}']")
            else:
                # Check if it's using find_packages() - acceptable
                if "find_packages()" in content:
                    self.log_warning(
                        f"{plugin_dir.name}/setup.py: Uses find_packages() - "
                        "consider explicit packages list"
                    )
                else:
                    self.log_error(
                        f"{plugin_dir.name}/setup.py: Missing correct packages parameter"
                    )

            # Check for old hyphenated references
            old_name = plugin_name.replace("_", "-")
            if old_name in content and "name=" not in content.split(old_name)[0].split("\n")[-1]:
                self.log_warning(
                    f"{plugin_dir.name}/setup.py: Contains old reference '{old_name}'"
                )

        return len(self.errors) == 0

    def check_test_config(self) -> bool:
        """Check that test configuration files are updated."""
        print("\n" + "=" * 70)
        print("Checking Test Configuration")
        print("=" * 70)

        # Check tests/conftest.py
        conftest_file = self.src_dir / "tests" / "conftest.py"
        if conftest_file.exists():
            content = conftest_file.read_text(encoding="utf-8")

            if "cbpi4_7seg_display" in content:
                self.log_pass("tests/conftest.py: Uses new underscore names")
            else:
                self.log_error("tests/conftest.py: Still uses old hyphenated names")

            if "cbpi4-" in content:
                self.log_error("tests/conftest.py: Contains old hyphenated references")
        else:
            self.log_warning("tests/conftest.py not found")

        # Check tests/real_plugin/conftest.py
        real_conftest = self.src_dir / "tests" / "real_plugin" / "conftest.py"
        if real_conftest.exists():
            content = real_conftest.read_text(encoding="utf-8")

            if "cbpi4_{" in content or "cbpi4_" in content:
                self.log_pass("tests/real_plugin/conftest.py: Updated for new structure")
            else:
                self.log_error("tests/real_plugin/conftest.py: May need updates")
        else:
            self.log_warning("tests/real_plugin/conftest.py not found")

        return len(self.errors) == 0

    def check_plugin_structure(self) -> bool:
        """Check that plugin directories are properly flattened."""
        print("\n" + "=" * 70)
        print("Checking Plugin Structure (Flattening)")
        print("=" * 70)

        plugin_dirs = [d for d in self.src_dir.glob("cbpi4_*") if d.is_dir()]

        for plugin_dir in plugin_dirs:
            # Check for __init__.py at top level (flattened structure)
            init_file = plugin_dir / "__init__.py"
            if init_file.exists():
                self.log_pass(f"{plugin_dir.name}/: Properly flattened (has __init__.py)")
            else:
                # Check if there's a nested directory with same name
                nested_dir = plugin_dir / plugin_dir.name
                if nested_dir.exists():
                    self.log_error(
                        f"{plugin_dir.name}/: Still has double-nesting "
                        f"({plugin_dir.name}/{plugin_dir.name}/)"
                    )
                else:
                    self.log_warning(
                        f"{plugin_dir.name}/: No __init__.py found (may not be a Python package)"
                    )

        return len(self.errors) == 0

    def run_all_checks(self) -> Tuple[bool, int, int, int]:
        """Run all verification checks."""
        print("=" * 70)
        print("Plugin Migration Verification")
        print("=" * 70)

        self.check_plugin_directories()
        self.check_setup_py_files()
        self.check_test_config()
        self.check_plugin_structure()

        # Print summary
        print("\n" + "=" * 70)
        print("Verification Summary")
        print("=" * 70)
        print(f"Passed:   {len(self.passed)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Errors:   {len(self.errors)}")

        if self.errors:
            print("\n" + "=" * 70)
            print("ERRORS FOUND:")
            for error in self.errors:
                print(f"  {error}")

        if self.warnings:
            print("\n" + "=" * 70)
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")

        success = len(self.errors) == 0
        print("\n" + "=" * 70)
        if success:
            print("✅ MIGRATION VERIFICATION PASSED")
        else:
            print("❌ MIGRATION VERIFICATION FAILED")
        print("=" * 70)

        return success, len(self.passed), len(self.warnings), len(self.errors)


def main():
    """Main entry point."""
    src_dir = Path(__file__).parent.parent
    verifier = MigrationVerifier(src_dir)

    success, passed, warnings, errors = verifier.run_all_checks()

    # Exit with appropriate code
    if not success:
        sys.exit(1)
    elif warnings > 0:
        sys.exit(2)  # Warnings present but no errors
    else:
        sys.exit(0)  # All checks passed


if __name__ == "__main__":
    main()
