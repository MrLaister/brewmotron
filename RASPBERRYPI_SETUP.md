# Raspberry Pi Setup for Brewmotron

This guide will help you set up your Raspberry Pi to run the Brewmotron brewing automation system.

## Prerequisites

- Raspberry Pi (Zero/Zero 2 W recommended, any Pi model supported)
- MicroSD card (16GB or larger recommended)
- Raspberry Pi OS Lite installed and running
- Network connection (WiFi or Ethernet)

## Initial Setup

### 1. Enable SSH (Optional but Recommended)

SSH access allows you to manage your Brewmotron remotely without connecting a keyboard/monitor.

#### Method 1: Using raspi-config (if you have direct access)
```bash
sudo raspi-config
```
- Navigate to "Interface Options"
- Select "SSH" 
- Choose "Yes" to enable SSH
- Select "Finish" and reboot when prompted

#### Method 2: Enable SSH before first boot
If setting up a fresh SD card:
1. After flashing Raspberry Pi OS to your SD card
2. Create an empty file named `ssh` (no extension) in the boot partition
3. This will enable SSH on first boot

#### Method 3: Using systemctl (command line)
```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

### 2. Set Network Hostname

Configure your Pi to be accessible via a friendly network name instead of just IP address.

#### Set the hostname to "brewmotron"
```bash
sudo hostnamectl set-hostname brewmotron
```

#### Update /etc/hosts file
```bash
sudo nano /etc/hosts
```
Change the line that reads:
```
127.0.1.1    raspberrypi
```
to:
```
127.0.1.1    brewmotron
```

#### Restart networking service
```bash
sudo systemctl restart systemd-hostnamed
sudo reboot
```

After reboot, you should be able to access your Brewmotron system at:
- **Web Interface**: `http://brewmotron:8000` (or `https://brewmotron:8000` if SSL is configured)
- **SSH Access**: `ssh pi@brewmotron` (replace 'pi' with your username)

## Network Access

Once configured, users on the same network can access Brewmotron by typing `brewmotron:8000` in their web browser instead of needing to know the IP address.

**Note**: The hostname resolution depends on your network router's mDNS/Bonjour support. If `brewmotron:8000` doesn't work, you may need to use `brewmotron.local:8000` or fall back to the IP address.

## Next Steps

After completing this basic setup:
1. Install CraftBeerPi4 and Brewmotron plugins (see main README.md)
2. Configure your brewing hardware connections
3. Set up the web interface for your specific brewing setup

## Troubleshooting

### Can't connect via hostname
- Try `brewmotron.local:8000` instead
- Check that both devices are on the same network
- Verify the hostname was set correctly: `hostname`
- Fall back to IP address if needed: `ip addr show`

### SSH Connection Issues
- Verify SSH is enabled: `sudo systemctl status ssh`
- Check firewall settings if using one
- Ensure you're using the correct username (default is usually `pi`)