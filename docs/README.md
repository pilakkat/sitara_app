# SITARA Documentation

Welcome to the SITARA Robot Fleet Management System documentation. This folder contains comprehensive guides for all aspects of the system.

## � Quick Reference Table

| Document | Category | Description |
|----------|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System | Client architecture, design patterns, and components |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | System | Recent features: session timeout, client database |
| [BATTERY_DISPLAY_UPDATE.md](BATTERY_DISPLAY_UPDATE.md) | Feature | Battery display with percentage and visual indicators |
| [VERSION_MANAGEMENT_GUIDE.md](VERSION_MANAGEMENT_GUIDE.md) | Feature | Software version tracking for robot controllers |
| [CLIENT_DATABASE.md](CLIENT_DATABASE.md) | Feature | Local SQLite database for version & credentials |
| [PASSWORD_SYNC.md](PASSWORD_SYNC.md) | Feature | Password synchronization and persistence |
| [CREDENTIALS.md](CREDENTIALS.md) | Config | Credential management and security |
| [GUNICORN_DEPLOYMENT.md](GUNICORN_DEPLOYMENT.md) | Deploy | Production deployment with Gunicorn |

## �📖 Documentation Overview

### System Architecture & Design
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed client architecture, design patterns, and system components
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Summary of recent features including session timeout and client database

### Features & Capabilities
- **[BATTERY_DISPLAY_UPDATE.md](BATTERY_DISPLAY_UPDATE.md)** - Battery display implementation with percentage calculation and visual indicators
- **[VERSION_MANAGEMENT_GUIDE.md](VERSION_MANAGEMENT_GUIDE.md)** - Software version tracking system for robot controllers (RCPCU, RCSPM, RCMMC, RCPMU)
- **[CLIENT_DATABASE.md](CLIENT_DATABASE.md)** - Local SQLite database for client-side version tracking, user credentials, and update management
- **[PASSWORD_SYNC.md](PASSWORD_SYNC.md)** - Password synchronization between retry authentication and database persistence

### Configuration & Deployment
- **[CREDENTIALS.md](CREDENTIALS.md)** - Credential management, environment configuration, and security best practices
- **[GUNICORN_DEPLOYMENT.md](GUNICORN_DEPLOYMENT.md)** - Production deployment guide using Gunicorn WSGI server

## 🚀 Quick Navigation

### For New Users
1. Start with the [main README](../README.md) for system overview
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design
3. Follow [CREDENTIALS.md](CREDENTIALS.md) for initial setup
4. Consult [../client/README.md](../client/README.md) for client installation

### For Developers
1. Read [ARCHITECTURE.md](ARCHITECTURE.md) for code organization
2. Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for recent changes
3. Check feature-specific docs for implementation details
4. See [GUNICORN_DEPLOYMENT.md](GUNICORN_DEPLOYMENT.md) for deployment strategies

### For Operators
1. Review [VERSION_MANAGEMENT_GUIDE.md](VERSION_MANAGEMENT_GUIDE.md) for software updates
2. Understand [BATTERY_DISPLAY_UPDATE.md](BATTERY_DISPLAY_UPDATE.md) for battery monitoring
3. Learn [PASSWORD_SYNC.md](PASSWORD_SYNC.md) for credential management
4. Reference [CLIENT_DATABASE.md](CLIENT_DATABASE.md) for database operations

## 📂 Document Categories

### Technical Documentation
- Architecture & Design
- Implementation Details
- Database Schema

### Feature Documentation
- Battery Management
- Version Tracking
- Password Synchronization

### Operations Documentation
- Deployment Guides
- Configuration Management
- Security & Credentials

## 🔗 Related Resources

- **[Main Project README](../README.md)** - Project overview and installation
- **[Client README](../client/README.md)** - Client application guide
- **[SystemD Service](../client/systemd/README.md)** - Linux service configuration

---

**Last Updated:** December 1, 2025  
**Project:** SITARA Robot Fleet Management System  
**Version:** 1.0.0
