# GPS Tracker System

## Overview
This system is a Python-based GPS tracking and BLE scanning solution designed to run on Raspberry Pi OS (Lite) with a Qualcomm SIM7000E GSM/GPS module. The system provides real-time location tracking, BLE device scanning, and network connectivity over both GSM and WiFi interfaces.

## Architecture

### Core Components
1. **Main Controller (supervisor.py)**
   - Manages all system threads and components
   - Handles error states and recovery
   - Coordinates tasks timing and execution

2. **Modem Management (modemdler.py)**
   - Controls the SIM7000E GSM/GPS modem
   - Handles hardware power management
   - Provides communication layer initialization

3. **Network Management (networker.py)**
   - Monitors network connectivity (GSM and WiFi)
   - Manages connection states and transitions
   - Implements UDP packet transmission
   - Handles bearer network activation/deactivation

4. **BLE Scanner (blendler.py)**
   - Scans for BLE devices
   - Filters and tracks device presence
   - Maintains device histories and visibility states

5. **Data Packaging (packager.py)**
   - Coordinates GPS data acquisition
   - Builds data packets with GPS, BLE, and system info
   - Manages packet queuing and transmission

6. **AT Command Interface (commander.py)**
   - Provides AT command functions for the modem
   - Implements cellular, HTTP, and GPS functions
   - Handles PDP context and bearer management

7. **Serial Communication (serialer.py)**
   - Manages serial port communication with the modem
   - Handles timeout detection and recovery
   - Processes AT command responses

8. **Firmware & Config Updates (updater.py)**
   - Manages remote firmware updates
   - Downloads and applies configuration changes
   - Handles WiFi network configuration

9. **Support Utilities (support.py)**
   - Provides logging functionality
   - Implements system shell command execution
   - Handles time synchronization and formatting utilities

### Key Features
- **Dual Network Connectivity**: Seamless switching between GSM and WiFi networks
- **GPS Tracking**: Real-time GPS location tracking with adjustable intervals
- **BLE Device Scanning**: Detection and tracking of nearby BLE devices
- **Remote Management**: OTA firmware updates and remote configuration
- **Adaptive Reporting**: Dynamic reporting frequency based on movement detection
- **Encrypted Communications**: Data encryption using Salsa20 cipher
- **Resilient Operation**: Automatic recovery from errors and connection failures
- **Power Management**: Optimized power usage based on movement state

## Technical Specifications

### Hardware Requirements
- Raspberry Pi 0w or compatible
- Qualcomm SIM7000E GSM/GPS modem
- UART interface connection between Pi and modem

### Communication
- **Uplink**: UDP packets containing GPS coordinates, BLE device info, and system status
- **Downlink**: HTTP GET requests for configuration and firmware updates
- **Local**: UART communication with modem via AT commands

### System Behavior
- **Movement Detection**: Adapts reporting frequency based on detected movement
- **Connection Management**: Prioritizes WiFi over GSM when available
- **Error Recovery**: Implements multi-level error recovery strategies
- **Data Persistence**: Maintains operation through connectivity outages with packet queuing

### Configuration
- **Remote Configuration**: Updates APN, PIN, and WiFi settings from server
- **Firmware Updates**: OTA firmware updates with version tracking and rollback capability
- **Time Synchronization**: GPS-based time synchronization

## Error Handling Codes
The system implements a hierarchical error handling system:

- **W0, W1**: System-level errors requiring reboot or process restart
- **M0-M3**: Modem-related errors requiring various recovery actions
- **N0-N2**: Network-related errors or state changes
- **U0-U2**: Update-related errors or actions