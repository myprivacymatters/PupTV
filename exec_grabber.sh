#!/bin/bash
python3 -m pip install --upgrade yt-dlp
python3 YouTubeLinkGrabber.py > ./youtube.m3u8
echo M3U update complete.
