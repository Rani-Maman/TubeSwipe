# TubeSwipe

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-modern-green)

A swipe-based YouTube video discovery application for efficiently browsing and organizing videos from your subscriptions.

<img width="646" height="904" alt="image" src="https://github.com/user-attachments/assets/f8ce851d-7897-4d91-9722-dbc1db7688ac" />

## Overview

TubeSwipe provides a swiping-style interface for managing YouTube content, allowing users to quickly swipe through their subscription feed and organize videos into playlists. The app integrates AI-powered summaries and provides an intuitive keyboard-driven workflow.

## Prerequisites

- **Python 3.8+** installed
- **Google Cloud Project** with YouTube Data API v3 enabled
  - Create project at [Google Cloud Console](https://console.cloud.google.com/)
  - Enable YouTube Data API v3
  - Create OAuth 2.0 credentials (Desktop application type)
  - Download client secrets JSON file
- **AI API Key** (at least one required):
  - [Gemini API](https://ai.google.dev/) (Free) - Recommended
  - [OpenAI API](https://platform.openai.com/api-keys) (Paid alternative)

## Tech Stack

- **Backend**: Python 3.8+, FastAPI
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Authentication**: Google OAuth 2.0
- **APIs**: YouTube Data API v3, Google Gemini API
- **Session Management**: Starlette Sessions

## Key Features

- **Swipe Interface**: Intuitive left/right swipe gestures (mouse & touch support)
- **AI Summaries**: Gemini-powered video summaries with caching
- **Playlist Management**: Create and organize videos into custom playlists
- **Channel Filtering**: Mute channels to curate your feed
- **Keyboard Shortcuts**: Arrow keys for efficient navigation (← skip, → save, ↓ undo)
- **Shorts Toggle**: Filter YouTube Shorts on/off
- **Responsive Design**: Mobile-first UI with gradient aesthetics

## Architecture

- **RESTful API**: FastAPI endpoints for feed, playlists, summaries, and user actions
- **State Management**: Session-based authentication with OAuth token refresh
- **Data Persistence**: JSON-based storage for user preferences and muted channels
- **Asynchronous Operations**: Async feed fetching for improved performance

## Project Structure

```
TubeSwipe/
├── app/
│   ├── services/       # Business logic (YouTube, summaries, storage)
│   ├── auth.py         # OAuth flow
│   ├── config.py       # Environment configuration
│   ├── main.py         # FastAPI routes
│   └── models.py       # Pydantic models
├── templates/          # Jinja2 templates
├── tests/              # Unit tests
└── requirements.txt    # Python dependencies
```

