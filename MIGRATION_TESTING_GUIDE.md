# Plugin Migration Testing Guide

**Date**: November 30, 2024
**Purpose**: Comprehensive testing after plugin directory migration

---

## Prerequisites

1. **Start Docker Desktop** (required for Docker-based testing)
2. Ensure you're in the project root: `cd C:\Users\andre\Nextcloud\Projects\ClaudeCode\brewmotron`

---

## Quick Verification (Manual)

Before running full tests, verify the migration manually:

### 1. Check Plugin Directories

```bash
cd src
ls -d cbpi4_*
```

**Expected output** (10 directories):
```
cbpi4_7seg_display
cbpi4_always_on_gpio
cbpi4_bmt_key
cbpi4_bmt_momentary_buttons
cbpi4_gpio_input
cbpi4_i2c_temp_sensor
cbpi4_internet_connected_gpio
cbpi4_lcd_display
cbpi4_nor3
cbpi4_one_at_a_time
```

### 2. Verify No Old Directories Exist

```bash
ls -d cbpi4-* 2>&1
```

**Expected output**:
```
ls: cannot access 'cbpi4-*': No such file or directory
```

### 3. Check Sample setup.py

```bash
grep "packages=" cbpi4_7seg_display/setup.py
```

**Expected output**:
```python
    packages=["cbpi4_7seg_display"],
```

---

## Full Test Suite (Docker-based)

### Test 1: Ubuntu Docker Environment

**Build the Ubuntu test image:**
```bash
cd C:\Users\andre\Nextcloud\Projects\ClaudeCode\brewmotron
docker build -f local_test/Dockerfile.test -t brewmotron-test:latest .
```

**Run unit tests:**
```bash
docker run --rm brewmotron-test:latest python3 run_tests.py unit
```

**Expected result:**
- **63 cache handler tests PASS** ✅
- **Coverage**: 97%+ for `brewmotron_cache_handler`
- **No import errors**
- **All tests complete in ~10-15 seconds**

**Run all tests:**
```bash
docker run --rm brewmotron-test:latest python3 run_tests.py all
```

**Expected result:**
- **63 tests PASS** (Phase 1: only cache handler tests active)
- **86 plugin tests SKIPPED** (Phase 2: awaiting cache handler integration)
- **39 integration tests SKIPPED** (Phase 2)

### Test 2: Raspbian Docker Environment (ARM Emulation)

**Build the Raspbian test image:**
```bash
docker buildx build --platform linux/arm64 \
  -f local_test/Dockerfile.test \
  -t brewmotron-test-raspbian:latest \
  .
```

**Note**: First build may take 5-10 minutes due to QEMU ARM64 emulation

**Run unit tests:**
```bash
docker run --rm --platform linux/arm64 brewmotron-test-raspbian:latest python3 run_tests.py unit
```

**Expected result:**
- Same as Ubuntu (63 tests PASS)
- Slower execution due to QEMU emulation

---

## Migration Verification Script

**Run automated verification** (when Python is available):

```bash
cd src
python scripts/verify_migration.py
```

**What it checks:**
- ✅ All plugin directories use underscores
- ✅ No old hyphenated directories exist
- ✅ All setup.py files reference correct module names
- ✅ Test configuration files updated
- ✅ Plugin structure properly flattened

**Expected output:**
```
✅ MIGRATION VERIFICATION PASSED
Passed:   XX
Warnings: 0
Errors:   0
```

---

## Test Results Checklist

After running tests, verify:

- [ ] **Ubuntu Docker tests pass** - 63/63 tests
- [ ] **Raspbian Docker tests pass** - 63/63 tests (slower but same results)
- [ ] **No import errors** - All plugin modules load correctly
- [ ] **Coverage >97%** - brewmotron_cache_handler module
- [ ] **Migration script passes** - No errors, only warnings acceptable
- [ ] **Plugin directories correct** - All use underscores
- [ ] **setup.py files updated** - All reference new module names

---

## If Tests Fail

### Import Errors

If you see errors like:
```
ModuleNotFoundError: No module named 'cbpi4-7SegDisplay'
```

**Solution**: Check that test configuration files were updated:
- `tests/conftest.py` - Should use `cbpi4_7seg_display`
- `tests/real_plugin/conftest.py` - Should handle new naming

### Directory Not Found Errors

If you see:
```
FileNotFoundError: Plugin source not found: cbpi4-GPIOInput
```

**Solution**: Verify all old directories were removed and new ones created

### setup.py Errors

If you see:
```
error: can't find package 'cbpi4-GPIOInput'
```

**Solution**: Check setup.py `packages=` parameter uses underscores

---

## Alternative: Quick Smoke Test (Without Docker)

If Docker isn't available, run basic Python import test:

```bash
cd src
python3 -c "import sys; sys.path.insert(0, '.'); import cbpi4_7seg_display; print('✅ Import successful')"
```

**Expected output:**
```
✅ Import successful
```

Try for multiple plugins:
```bash
for plugin in cbpi4_7seg_display cbpi4_gpio_input cbpi4_cache_handler; do
  python3 -c "import sys; sys.path.insert(0, '.'); import $plugin; print('✅ $plugin imports successfully')" 2>&1 || echo "❌ $plugin import failed"
done
```

---

## Docker Commands Reference

### Useful Docker Commands

**Check Docker is running:**
```bash
docker --version
docker ps
```

**View Docker images:**
```bash
docker images | grep brewmotron
```

**Remove old test images** (if needed):
```bash
docker rmi brewmotron-test:latest
docker rmi brewmotron-test-raspbian:latest
```

**Run interactive shell in container** (for debugging):
```bash
docker run --rm -it brewmotron-test:latest /bin/bash
```

---

## Success Criteria

The migration is **fully successful** if:

1. ✅ **All 10 plugin directories** renamed and flattened
2. ✅ **All setup.py files** reference new module names
3. ✅ **Tests pass** in both Ubuntu and Raspbian Docker environments
4. ✅ **No import errors** when loading plugins
5. ✅ **Coverage >97%** for cache handler
6. ✅ **Migration verification** script passes
7. ✅ **Documentation updated** with new naming convention

---

## Next Steps After Testing

Once all tests pass:

1. **Commit the changes:**
   ```bash
   cd src
   git status
   git add .
   git commit -m "Migrate plugin directories from hyphens to underscores (PEP 8)"
   ```

2. **Continue with Phase 2:**
   - Refactor plugins to use cache handler
   - Re-enable plugin unit tests
   - Add plugin coverage to GitHub Actions

---

## Troubleshooting

### Docker Desktop Not Running

**Symptoms:**
```
ERROR: error during connect: ... dockerDesktopLinuxEngine: The system cannot find the file specified
```

**Solution:**
1. Start Docker Desktop application
2. Wait for Docker to fully start (whale icon in system tray)
3. Retry docker commands

### Permission Issues (Windows)

If you get permission errors:
1. Run PowerShell or Command Prompt as Administrator
2. Or adjust Docker Desktop settings for file sharing

### QEMU Not Available (Raspbian tests)

If ARM64 emulation fails:
```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

---

## Contact & Support

For issues with this migration:
- Review: `src/PLUGIN_MIGRATION_2024-11-30.md`
- Check: `CLAUDE.md` memories section
- Verify: Migration scripts in `scripts/` directory

---

**Document Version**: 1.0
**Last Updated**: November 30, 2024
