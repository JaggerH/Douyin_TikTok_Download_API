# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Douyin_TikTok_Download_API is a high-performance asynchronous API service for downloading and parsing video data from Douyin (抖音), TikTok, and Bilibili. The project provides both RESTful APIs and a web interface for batch processing video URLs.

## Architecture

The project follows a modular architecture with clear separation between API endpoints, web interface, and platform-specific crawlers:

### Core Components
- **`/app/api/`**: FastAPI-based REST API endpoints with automatic documentation
- **`/app/web/`**: PyWebIO-based web interface for batch URL processing  
- **`/crawlers/`**: Platform-specific data extraction modules
- **`/chrome-cookie-sniffer/`**: Chrome extension for dynamic cookie updates

### Platform Support
- **Douyin (抖音)**: Chinese TikTok with X-Bogus and A-Bogus algorithms
- **TikTok**: International version with web and mobile app APIs
- **Bilibili**: Chinese video platform with comprehensive video/user data APIs
- **Hybrid parsing**: Automatic platform detection and unified processing

### Request Flow
1. API receives video URLs through REST endpoints or web interface
2. Hybrid parser identifies platform and delegates to appropriate crawler
3. Platform crawlers use configured cookies/tokens to access APIs
4. Data is processed, validated, and returned in standardized format
5. Optional download functionality provides direct video file access

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server with auto-reload
python start.py
```

### Production Deployment

#### Docker (Recommended)
```bash
# Build and run with Docker
docker pull evil0ctal/douyin_tiktok_download_api:latest
docker run -d --name douyin_tiktok_api -p 80:80 evil0ctal/douyin_tiktok_download_api

# Or build locally
docker build -t douyin_tiktok_api .
docker run -d -p 80:80 douyin_tiktok_api
```

#### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Update configuration and restart
docker-compose down
docker-compose up -d
```

### Linux System Deployment
```bash
# One-click installation script
wget -O install.sh https://raw.githubusercontent.com/Evil0ctal/Douyin_TikTok_Download_API/main/bash/install.sh
sudo bash install.sh

# Service management
sudo systemctl start Douyin_TikTok_Download_API.service
sudo systemctl stop Douyin_TikTok_Download_API.service
sudo systemctl enable Douyin_TikTok_Download_API.service

# Update project
cd /www/wwwroot/Douyin_TikTok_Download_API/bash
sudo bash update.sh
```

## Configuration Management

### Main Configuration (`config.yaml`)
- **API settings**: Host, port, docs URLs, download paths
- **Web interface**: PyWebIO theme, URL limits, Easter egg features
- **iOS Shortcut**: Integration settings for mobile shortcuts

### Platform-Specific Cookies and Headers
**Critical**: Cookie management is essential for bypassing platform restrictions:

- **Douyin**: `crawlers/douyin/web/config.yaml` - Requires valid login cookies
- **TikTok**: `crawlers/tiktok/web/config.yaml` - Web session cookies needed
- **Bilibili**: `crawlers/bilibili/web/config.yaml` - Authentication headers

### Cookie Update Workflow
1. Use `chrome-cookie-sniffer` extension to monitor browser cookies
2. Extension automatically detects Douyin domain activity
3. Webhook notifications trigger cookie updates in production
4. Manual updates required for TikTok and Bilibili platforms

## API Architecture

### Endpoint Structure
```
/api/hybrid/* - Platform-agnostic parsing endpoints
/api/douyin/web/* - Douyin-specific data endpoints
/api/tiktok/web/* - TikTok web API endpoints
/api/tiktok/app/* - TikTok mobile app endpoints
/api/bilibili/web/* - Bilibili data endpoints
/api/download - Direct video download endpoint
/api/ios/* - iOS Shortcut integration endpoints
```

### Key APIs
- **Hybrid parsing**: `/api/hybrid/video_data` - Auto-detect platform and extract data
- **Batch processing**: Web interface supports up to 30 URLs simultaneously
- **Download service**: `/api/download` - Handles platform-specific download logic
- **User data**: Profile information, followers, video collections per platform

## Security and Authentication

### Anti-Bot Measures
- **X-Bogus/A-Bogus algorithms**: Custom signature generation for Douyin/TikTok
- **Dynamic headers**: User-Agent rotation and browser fingerprinting
- **Cookie validation**: Regular cookie refresh to maintain access
- **Rate limiting**: Built-in request throttling

### Cookie Risk Control
- Deploy to servers with normal Douyin/TikTok access (preferably US regions)
- Use logged-in account cookies for better success rates
- Monitor for cookie expiration and 403/429 response codes
- Implement automatic cookie refresh via Chrome extension

## Development Patterns

### Adding New Platform Support
1. Create crawler module in `/crawlers/{platform}/`
2. Implement base crawler interface with required methods
3. Add configuration file for headers/cookies
4. Create API endpoints in `/app/api/endpoints/`
5. Update router configuration and main app

### Error Handling
- Platform-specific exceptions in `crawlers/utils/api_exceptions.py`
- Graceful fallbacks when APIs are unavailable
- Comprehensive logging for debugging platform changes

### Testing Considerations
- Cookie-dependent functionality requires valid authentication
- Platform APIs change frequently - monitor for breaking changes
- Test with various URL formats per platform
- Validate download functionality separately from parsing

## Important Notes

### Deployment Considerations
- **Regional restrictions**: Deploy to regions with platform access
- **Resource usage**: Video downloading is resource-intensive
- **Cookie management**: Plan for regular cookie updates
- **Legal compliance**: Respect platform terms of service and copyright

### Platform-Specific Issues
- **Douyin**: Strict anti-bot measures, requires frequent cookie updates
- **TikTok**: Download links expire quickly, use `/api/download` endpoint
- **Bilibili**: Complex video stream handling, multiple quality options

### Chrome Extension Integration
The `chrome-cookie-sniffer` extension provides automated cookie management:
- Monitors Douyin domain for cookie changes
- Sends webhook notifications on updates  
- Supports dynamic configuration via update-cookie endpoint
- Currently focused on Douyin platform only