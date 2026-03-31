import json
import os
import subprocess
from datetime import datetime
import gspread
import time
from google.oauth2.service_account import Credentials
import base64
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration constants
FONT_PATH = os.path.abspath("font.ttf")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FONT_SIZE = 80
LINE_SPACING = 12
DEFAULT_DURATION = 2.5
TEXT_Y_OFFSET = -100

# Watermark configuration
WATERMARK_TEXT = "@faithflow"
WATERMARK_FONTSIZE = 36
WATERMARK_FONTCOLOR = "white@0.4"
WATERMARK_SHADOWCOLOR = "black"
WATERMARK_SHADOWX = 2
WATERMARK_SHADOWY = 2
WATERMARK_Y_OFFSET = 120

# Temporary files
TEMP_TEXT_FILE = "temp.txt"
FILE_LIST_FILE = "file_list.txt"
OUTPUT_FOLDER = "videos"

def get_user_scenes():
    """
    Get scenes from environment variables (for GitHub Actions)
    Fallback to manual input if not provided
    """
    scenes = []

    for i in range(1, 6):
        text = os.getenv(f"LINE_{i}")
        if not text:
            text = input(f"Enter line {i}: ")

        text = text.replace("\\n", "\n")
        scenes.append(text)

    return scenes

def create_scene(text, output, duration=DEFAULT_DURATION):
    """
    Create a vertical video scene with text overlay on a black background.
    
    Args:
        text: The text to display in the scene
        output: Output video file path
        duration: Duration of the video in seconds (default: 3)
    """
    # Write text to temporary file for ffmpeg processing
    temp_file = f"temp_{output}.txt"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(text)

    # Build ffmpeg command to create text overlay video
    video_size = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"
    # Main text
    main_text_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"textfile={temp_file}:"
        f"fontcolor=white:"
        f"fontsize={FONT_SIZE}:"
        f"line_spacing={LINE_SPACING}:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2+{TEXT_Y_OFFSET}"
    )

    # Watermark
    safe_watermark = WATERMARK_TEXT.replace("'", "\\'")

    watermark_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"text='{safe_watermark}':"
        f"fontcolor={WATERMARK_FONTCOLOR}:"
        f"fontsize={WATERMARK_FONTSIZE}:"
        f"shadowcolor={WATERMARK_SHADOWCOLOR}:shadowx={WATERMARK_SHADOWX}:shadowy={WATERMARK_SHADOWY}:"
        f"x=(w-text_w)/2:"
        f"y=h-{WATERMARK_Y_OFFSET}"
    )

    drawtext_filter = f"{main_text_filter},{watermark_filter}"

    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", f"color=c=black:s={video_size}:d={duration}",
        "-vf", drawtext_filter,
        "-y",
        output
    ]

    print(f"\n🎬 Creating scene: {output}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print("❌ FFmpeg error:")
        print(result.stderr.decode())
        exit()

    # Verify the scene was created successfully
    if not os.path.exists(output):
        print(f"❌ Failed to create {output}")
        exit()
    
    # Clean up temporary text file
    if os.path.exists(temp_file):
        os.remove(temp_file)

from google.auth.transport.requests import Request

def upload_to_youtube(video_file, title):
    print("📤 Uploading to YouTube...")

    token_env = os.getenv("YOUTUBE_TOKEN")

    if not token_env:
        print("❌ YOUTUBE_TOKEN not found")
        return

    token_data = base64.b64decode(token_env)

    with open("token.pickle", "wb") as f:
        f.write(token_data)

    with open("token.pickle", "rb") as f:
        creds = pickle.load(f)

    # 🔥 Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": f"{title}... ❤️ #shorts",
                "description": "Follow @faithflow 🙏\n#shorts #faith #jesus",
                "tags": ["faith", "jesus", "motivation", "shorts"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "public"
            }
        },
        media_body=MediaFileUpload(video_file)
    )

    response = request.execute()
    print("✅ Uploaded:", response["id"])

def get_scenes_from_sheet():
    scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key("1mw8hbnpAAtyna4kpM7lale04HxF4rg4tFooFT1M7VnI").sheet1
    rows = sheet.get_all_records()

    for i, row in enumerate(rows):
        if row.get("Status", "") != "DONE":
            scenes = [
                row.get("Hook", ""),
                row.get("Emotion", ""),
                row.get("Struggle", ""),
                row.get("Message", ""),
                row.get("Ending", "")
            ]
            return i + 2, scenes, sheet  # row index + data

    return None, None, sheet

def main():
    """Generate a vertical video with multiple text scenes and combine them."""
    
    # Ensure Google service account credentials file exists
    if not os.path.exists("credentials.json"):
        print("❌ credentials.json not found")
        exit()
    
    # Create output folder if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    row_index, scenes, sheet = get_scenes_from_sheet()

    if not scenes:
        print("No new data found")
        return
    
    # Step 1: Generate individual scene videos
    scene_files = []
    for i, text in enumerate(scenes[:5]):
        filename = f"scene_{i}.mp4"
        create_scene(text, filename)
        scene_files.append(filename)
    
    print(f"\n✅ Generated {len(scene_files)} scenes")

    # Step 2: Create a file list for ffmpeg concatenation
    with open(FILE_LIST_FILE, "w") as f:
        for file in scene_files:
            f.write(f"file '{file}'\n")

    # Step 3: Combine all scenes into final video
    output_filename = os.path.join(OUTPUT_FOLDER, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    print(f"\n🎥 Merging scenes into: {output_filename}")
    result = subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", FILE_LIST_FILE,
        "-c:v", "libx264",
        "-c:a", "aac",
        output_filename
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print("❌ FFmpeg error during concat:")
        print(result.stderr.decode())
        exit()

    print("✅ Video generated successfully!")
    time.sleep(2)
    upload_to_youtube(output_filename, scenes[0])
    
    # Mark row as done in sheet
    headers = sheet.row_values(1)
    if "Status" in headers:
        status_col = headers.index("Status") + 1
        sheet.update_cell(row_index, status_col, "DONE")
    else:
        print("⚠️ Status column not found")
    sheet.update_cell(row_index, status_col, "DONE")

    # Step 4: Clean up temporary files
    for file in scene_files:
        if os.path.exists(file):
            os.remove(file)
    
    if os.path.exists(FILE_LIST_FILE):
        os.remove(FILE_LIST_FILE)
    
    if os.path.exists(TEMP_TEXT_FILE):
        os.remove(TEMP_TEXT_FILE)

    print("Cleaned up temporary files")

if __name__ == "__main__":
    main()