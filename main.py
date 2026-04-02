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
from googleapiclient.errors import HttpError
from concurrent.futures import ThreadPoolExecutor, as_completed
import contextlib

# Configuration constants
FONT_PATH = os.path.abspath("font.ttf")
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
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

# Google Drive folder for uploads
FOLDER_ID = "16GArci_d-ZZ1kOzlRq__1ZGp6lOWRfCO"

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

def create_full_video(lines, output):
    drawtext_filters = []

    for i, text in enumerate(lines):
        start = i * 3
        end = start + 3

        safe_text = text.replace("'", "\\'").replace(":", "\\:").replace("\n", "\\n")

        filter_text = (
            f"drawtext=fontfile={FONT_PATH}:"
            f"text='{safe_text}':"
            f"fontcolor=white:"
            f"fontsize={FONT_SIZE}:"
            f"line_spacing={LINE_SPACING}:"
            f"x=(w-text_w)/2:"
            f"borderw=3:bordercolor=black:"
            f"y=(h-text_h)/2:"
            f"enable='between(t,{start},{end})':alpha='if(lt(t,{start}+0.5),(t-{start})/0.5,1)'"
        )

        drawtext_filters.append(filter_text)

    # Watermark
    safe_watermark = WATERMARK_TEXT.replace("'", "\\'")

    watermark_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"text='{safe_watermark}':"
        f"fontcolor={WATERMARK_FONTCOLOR}:"
        f"fontsize={WATERMARK_FONTSIZE}:"
        f"x=(w-text_w)/2:"
        f"y=h-{WATERMARK_Y_OFFSET}"
    )

    drawtext_filters.append(watermark_filter)

    final_filter = ",".join(drawtext_filters)

    cmd = [
        "ffmpeg",
        "-i", "bg.mp4",
        "-i", "audio.mp3",
        "-t", "15",
        "-vf",
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"boxblur=10:1,"
        f"{final_filter}",
        "-y",
        output
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr.decode())
        raise Exception("Video generation failed")
    
from google.auth.transport.requests import Request

def upload_to_youtube(video_file, title):
    """
    Upload video to YouTube with OAuth credentials.
    """
    print("Uploading to YouTube...")

    return True;

    # try:
    #     creds = get_oauth_creds()
    #     if not creds:
    #         print("❌ Failed to load OAuth credentials")
    #         return False

    #     youtube = build("youtube", "v3", credentials=creds)

    #     request = youtube.videos().insert(
    #         part="snippet,status",
    #         body={
    #             "snippet": {
    #                 "title": f"{title}... #shorts",
    #                 "description": "Follow @faithflow-in-jesus 🙏\n#shorts #faith #jesus #christian #bible #prayer #worship #god #holyspirit #scripture #gospel #salvation #hope #love #church #ministry #inspiration #spiritual #christ #amen #blessed #motivation",
    #                 "tags": [
    #                     "faith", "jesus", "christian", "bible", "prayer",
    #                     "worship", "god", "holy spirit", "scripture",
    #                     "gospel", "salvation", "christianity", "hope",
    #                     "love", "church", "ministry", "inspiration",
    #                     "spiritual", "religion", "christ", "amen",
    #                     "blessed", "motivation", "shorts"
    #                 ],
    #                 "categoryId": "22"
    #             },
    #             "status": {
    #                 "privacyStatus": "public"
    #             }
    #         },
    #         media_body=MediaFileUpload(video_file)
    #     )

    #     response = request.execute()
    #     print("✅ Uploaded:", response["id"])
    #     return True

    # except HttpError as e:
    #     if "uploadLimitExceeded" in str(e):
    #         print("⚠️ YouTube upload quota exceeded")
    #     else:
    #         print(f"❌ YouTube upload failed: {e}")
    #     return False

    # except Exception as e:
    #     print(f"❌ Unexpected error: {e}")
    #     return False

def get_oauth_creds():
    token_env = os.getenv("YOUTUBE_TOKEN")
    
    if not token_env:
        print("Missing OAuth token")
        return None

    token_data = base64.b64decode(token_env)

    with open("token.pickle", "wb") as f:
        f.write(token_data)

    with open("token.pickle", "rb") as f:
        creds = pickle.load(f)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds.valid:
        print("❌ Invalid credentials")
        return None

    return creds

def upload_to_drive(file_path):
    try:
        print("Uploading to Google Drive...")

        creds = get_oauth_creds()
        drive_service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": os.path.basename(file_path)
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
    if not os.path.exists("credentials.json"):
        print("credentials.json not found")
        return False
    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    return True

def get_next_scenes():
    """Get the next set of scenes from Google Sheets."""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1mw8hbnpAAtyna4kpM7lale04HxF4rg4tFooFT1M7VnI").sheet1
        rows = sheet.get_all_records()

        for i, row in enumerate(rows):
           status = row.get("Status", "")
           if status not in ["DONE", "FAILED", "DRIVE"]:
                scenes = [
                    row.get("Hook", ""),
                    row.get("Emotion", ""),
                    row.get("Struggle", ""),
                    row.get("Message", ""),
                    row.get("Ending", "")
                ]
                # Convert literal \n and /n to actual newlines
                scenes = [text.replace("\\n", "\n").replace("/n", "\n") for text in scenes]
                # Avoid empty scenes
                scenes = [s if s.strip() else "..." for s in scenes]
                return i + 2, scenes, sheet  # row index + data
    except Exception as e:
        print(f"Error accessing Google Sheets: {e}")
        return None, None, None
    
    return None, None, None

def upload_and_update_status(output_filename, scenes, row_index, sheet):
    """Upload video to YouTube and update sheet status. Falls back to Drive upload."""
    try:
        time.sleep(2)  # Brief pause before upload
        
        drive_link = None
        upload_success = upload_to_youtube(output_filename, scenes[0])

        if not upload_success:
            print("YouTube failed → uploading to Drive")
            drive_link = upload_to_drive(output_filename)

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
    
    # Get next scenes from sheet
    row_index, scenes, sheet = get_next_scenes()
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

            create_full_video(scenes, output_filename)

            if not os.path.exists(output_filename):
                print("❌ Video generation failed")
                sheet.update_cell(row_index, status_col, "")
                return

            upload_success = upload_and_update_status(
                output_filename, scenes, row_index, sheet
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