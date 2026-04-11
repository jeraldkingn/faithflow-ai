import json
import os
import subprocess
from datetime import datetime
from turtle import width
import gspread
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request

# Configuration constants
FONT_PATH = os.path.abspath("font.ttf")
FONT_SIZE = 80
LINE_SPACING = 12
DEFAULT_DURATION = 3
TEXT_Y_OFFSET = -100

# Watermark configuration
WATERMARK_TEXT = "@faithflow-in-jesus"
WATERMARK_FONTSIZE = 40
WATERMARK_FONTCOLOR = "white@0.5"
WATERMARK_SHADOWCOLOR = "black"
WATERMARK_SHADOWX = 2
WATERMARK_SHADOWY = 2
WATERMARK_Y_OFFSET = 500
WATERMARK_BOTTOM_MARGIN = 50

# Google Drive folder for uploads
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Temporary files
TEMP_TEXT_FILE = "temp.txt"
FILE_LIST_FILE = "file_list.txt"
OUTPUT_FOLDER = "videos"

@contextlib.contextmanager
def video_generation_context():
    """Context manager for video generation with automatic cleanup."""
    start_time = time.time()
    temp_files = []
    
    try:
        print(f"🎬 Starting video generation at {datetime.now().strftime('%H:%M:%S')}")
        yield temp_files
    finally:
        # Always cleanup temporary files
        cleanup_temp_files(temp_files)
        elapsed = time.time() - start_time
        print(f"⏱️ Total processing time: {elapsed:.1f} seconds")

def cleanup_temp_files(temp_files):
    """Clean up temporary files safely."""
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"⚠️ Failed to remove {file_path}: {e}")

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

        text = text.replace("\\n", "\n").replace("/n", "\n")
        scenes.append(text)

    return scenes

def create_full_video(lines, output, content_type):
    drawtext_filters = []

    if content_type == "shorts":
        scene_duration = 3
        width, height = 1080, 1920
        bg_video = "bg_shorts.mp4"
        bg_audio = "bg_shorts.mp3"
    else:
        scene_duration = 8
        width, height = 1920, 1080
        bg_video = "bg_long.MP4"
        bg_audio = "bg_long.mpeg"

    for i, text in enumerate(lines):
        start = i * scene_duration
        end = start + scene_duration

        safe_text = text.replace("'", "\\'").replace(":", "\\:")

        filter_text = (
            f"drawtext=fontfile={FONT_PATH}:"
            f"text='{safe_text}':"
            f"fontcolor=white:"
            f"fontsize={FONT_SIZE}:"
            f"line_spacing={LINE_SPACING}:"
            f"text_align=center:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2:"
            f"enable='between(t,{start},{end})':"
            f"alpha='if(lt(t,{start}+0.5),(t-{start})/0.5,1)'"
        )

        drawtext_filters.append(filter_text)

    # 🔹 Watermark
    safe_watermark = WATERMARK_TEXT.replace("'", "\\'")

    watermark_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"text='{safe_watermark}':"
        f"fontcolor={WATERMARK_FONTCOLOR}:"
        f"fontsize={WATERMARK_FONTSIZE}:"
        f"x=(w-text_w)/2:"
        f"y=h-text_h-{WATERMARK_BOTTOM_MARGIN}"
    )

    drawtext_filters.append(watermark_filter)

    final_filter = ",".join(drawtext_filters)

    # 🔹 Dynamic total duration
    total_duration = len(lines) * scene_duration

    cmd = [
        "ffmpeg",
        "-i", bg_video,
        "-i", bg_audio,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(total_duration),  # ✅ dynamic now
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"boxblur=10:1,"
        f"{final_filter}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-y",
        output
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr.decode())
        raise Exception("Video generation failed")
    

def upload_to_youtube(video_file, title, hashtags, bibleverse):
    """
    Upload video to YouTube with OAuth credentials.
    """
    print("Uploading to YouTube...")

    formatted_tags = " ".join(
    [f"#{tag.strip()}" for tag in hashtags.split(",") if tag.strip()]
    )

    description = (
        f"{bibleverse}\n\n"
        f"Follow @faithflow-in-jesus 🙏\n\n"
        f"{formatted_tags}"
    )

    try:
        creds = get_oauth_creds()
        if not creds:
            print("❌ Failed to load OAuth credentials")
            return False

        youtube = build("youtube", "v3", credentials=creds)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": f"{title} | {bibleverse[:50]}... #shorts",
                    "description": description,
                    "tags": [
                        "faith", "shorts", "jesus", "healing", "trust god"
                    ],
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
        return True

    except HttpError as e:
        if "uploadLimitExceeded" in str(e):
            print("⚠️ YouTube upload quota exceeded")
        else:
            print(f"❌ YouTube upload failed: {e}")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    

def get_oauth_creds():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    refresh_token = os.getenv("OAUTH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ Missing OAuth environment variables")
        return None

    creds = OAuthCredentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/drive.file"
        ]
    )

    try:
        creds.refresh(Request())
        return creds
    except Exception as e:
        print("❌ Token refresh failed:", e)
        return None    

def load_service_account():
    data = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    return ServiceAccountCredentials.from_service_account_info(
        json.loads(data),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )

def upload_to_drive(file_path):
    try:
        print("Uploading to Google Drive...")

        creds = get_oauth_creds()
        drive_service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": os.path.basename(file_path),
            "parents": [FOLDER_ID] if FOLDER_ID else []
        }

        media = MediaFileUpload(file_path, mimetype="video/mp4")

        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink"
        ).execute()

        print("Uploaded to Drive:", file.get("webViewLink"))
        return file.get("webViewLink")

    except Exception as e:
        print("Drive upload failed:", e)
        return None

def setup():
    """Setup and validate environment."""    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    return True

def get_next_content():
    """Get next content based on Type (shorts/long) from Google Sheets."""
    try:
        creds = load_service_account()
        client = gspread.authorize(creds)
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        sheet = client.open_by_key(sheet_id).sheet1
        rows = sheet.get_all_records()

        for i, row in enumerate(rows):
            status = row.get("Status", "")
            content_type = row.get("Type", "shorts").lower()

            if status not in ["DONE", "FAILED", "DRIVE"]:

                # 🔹 SHORTS
                if content_type == "shorts":
                    scenes = [
                        row.get("Hook", ""),
                        row.get("Emotion", ""),
                        row.get("Struggle", ""),
                        row.get("Message", ""),
                        row.get("Ending", "")
                    ]

                    scenes = [
                        text.replace("\\n", "\n").replace("/n", "\n")
                        for text in scenes
                    ]

                # 🔹 LONG VIDEO
                else:
                    def split_scenes(text):
                        if not text:
                            return []
                        return [
                            s.strip().replace("\\n", "\n").replace("/n", "\n")
                            for s in text.split("%") if s.strip()
                        ]

                    hook = split_scenes(row.get("Hook", ""))
                    story = split_scenes(row.get("Emotion", ""))
                    verse = split_scenes(row.get("Struggle", ""))
                    message = split_scenes(row.get("Message", ""))
                    ending = split_scenes(row.get("Ending", ""))

                    scenes = hook + story + verse + message + ending

                # fallback safety
                scenes = [s if s.strip() else "..." for s in scenes]

                hashtags = row.get("Hashtags", "")
                bibleverse = row.get("Bibleverse", "")

                return i + 2, scenes, hashtags, bibleverse, sheet, content_type

    except Exception as e:
        print(f"Error accessing Google Sheets: {e}")
        return None, None, None, None, None, None

    return None, None, None, None, None, None

def upload_and_update_status(output_filename, scenes, hashtags, bibleverse, row_index, sheet, content_type):
    """Upload video to YouTube and update sheet status. Falls back to Drive upload."""
    try:
        time.sleep(2)  # Brief pause before upload
        
        drive_link = None
        title = next(
            (
                s for s in scenes
                if s.strip() and s != "..." and len(s.strip()) > 10
            ),
            ""
        ).strip()

        title = title.replace("\n", " ").strip()

        final_title = title

        if bibleverse:
            final_title += f" | {bibleverse[:50]}"

        if content_type == "shorts":
            final_title += " #shorts"

        # 🚨 FINAL SAFETY CHECK
        if not final_title or len(final_title.strip()) < 10:
            final_title = "God has a message for you"

        # Clean encoding
        final_title = final_title.encode("utf-8", "ignore").decode("utf-8")

        print("FINAL TITLE CLEAN:", repr(final_title))

        upload_success = upload_to_youtube(output_filename, final_title, hashtags, bibleverse)

        if not upload_success:
            print("YouTube failed → uploading to Drive")
            # drive_link = upload_to_drive(output_filename)

        # Determine status based on results
        if upload_success:
            status = "DONE"
        elif drive_link:
            print("Fallback upload to Drive successful")
            status = "DRIVE"
        else:
            status = "FAILED"
        
        # Update status based on upload results
        headers = sheet.row_values(1)
        if "Status" in headers:
            status_col = headers.index("Status") + 1
            sheet.update_cell(row_index, status_col, status)
            print(f"Status updated to {status}")
        else:
            print("Status column not found")

        if drive_link and "DriveLink" in headers:
            link_col = headers.index("DriveLink") + 1
            sheet.update_cell(row_index, link_col, drive_link)
            print("Drive link saved to sheet")    
        
        return upload_success
    except Exception as e:
        print(f"Error during upload/update: {e}")
        return False

def cleanup(scene_files):
    """Clean up scene files (legacy function - now handled by context manager)."""
    # This function is kept for backward compatibility but cleanup is now automatic
    pass

def main():
    """Main workflow: generate and upload faith videos."""
    print("🚀 Starting FaithFlow AI Video Generator")
    
    # Setup
    if not setup():
        return
    
    row_index, scenes, hashtags, bibleverse, sheet, content_type = get_next_content()

    if not scenes:
        print("ℹ️ No new scenes to process")
        return
    
    # Get status column index (needed throughout function)
    headers = sheet.row_values(1)
    status_col = headers.index("Status") + 1 if "Status" in headers else None
    
    # Mark row as processing to prevent concurrent execution
    try:
        if status_col:
            sheet.update_cell(row_index, status_col, "PROCESSING")
            print("📝 Status updated to PROCESSING")
        else:
            print("⚠️ Status column not found")
    except Exception as e:
        print(f"❌ Error updating status to PROCESSING: {e}")
        return
    
    # Use context manager for automatic cleanup
    with video_generation_context():
        try:
            print("🎬 Creating full video...")

            output_filename = os.path.join(
                OUTPUT_FOLDER,
                f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            )

            create_full_video(scenes, output_filename, content_type)

            if not os.path.exists(output_filename):
                print("❌ Video generation failed")
                sheet.update_cell(row_index, status_col, "")
                return

            upload_success = upload_and_update_status(
                output_filename, scenes, hashtags, bibleverse, row_index, sheet, content_type
            )

            if upload_success:
                print("🎉 Done!")
            else:
                print("⚠️ Upload failed")

        except Exception as e:
            print(f"💥 Error: {e}")
            sheet.update_cell(row_index, status_col, "")

if __name__ == "__main__":
    main()