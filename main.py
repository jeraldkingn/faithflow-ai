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

def create_scene(text, output, duration=DEFAULT_DURATION):
    """
    Create a vertical video scene with text overlay on a black background.
    
    Args:
        text: The text to display in the scene
        output: Output video file path
        duration: Duration of the video in seconds (default: 3)
    """
    # Split text into lines for individual centering
    lines = text.split('\n')
    
    # Build ffmpeg command to create text overlay video
    video_size = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"
    
    # Create drawtext filters for each line, each centered individually
    drawtext_filters = []
    
    # Calculate starting Y position to center the entire block vertically
    total_lines = len(lines)
    line_height = FONT_SIZE + LINE_SPACING
    total_text_height = total_lines * line_height - LINE_SPACING  # Subtract extra spacing
    start_y = (VIDEO_HEIGHT - total_text_height) / 2 + TEXT_Y_OFFSET
    
    for i, line in enumerate(lines):
        if line.strip():  # Only add non-empty lines
            safe_line = line.replace("'", "\\'").replace(":", "\\:")
            y_position = start_y + i * line_height
            line_filter = (
                f"drawtext=fontfile={FONT_PATH}:"
                f"text='{safe_line}':"
                f"fontcolor=white:"
                f"fontsize={FONT_SIZE}:" 
                f"x=(w-text_w)/2:"
                f"y={y_position}"
            )
            drawtext_filters.append(line_filter)

    # Join all line filters with commas
    main_text_filter = ",".join(drawtext_filters)

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
        "-i", "bg.mp4",  # 🎬 your 15 sec video
        "-t", str(duration),  # optional trim
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},boxblur=10:1,{drawtext_filter}",
        "-y",
        output
    ]

    print(f"\nCreating scene: {output}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr.decode())
        exit()

    # Verify the scene was created successfully
    if not os.path.exists(output):
        print(f"Failed to create {output}")
        exit()

from google.auth.transport.requests import Request

def upload_to_youtube(video_file, title):
    """
    Upload video to YouTube with OAuth credentials.
    """
    print("Uploading to YouTube...")

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
                    "title": f"{title}... #shorts",
                    "description": "Follow @faithflow-in-jesus 🙏\n#shorts #faith #jesus #christian #bible #prayer #worship #god #holyspirit #scripture #gospel #salvation #hope #love #church #ministry #inspiration #spiritual #christ #amen #blessed #motivation",
                    "tags": [
                        "faith", "jesus", "christian", "bible", "prayer",
                        "worship", "god", "holy spirit", "scripture",
                        "gospel", "salvation", "christianity", "hope",
                        "love", "church", "ministry", "inspiration",
                        "spiritual", "religion", "christ", "amen",
                        "blessed", "motivation", "shorts"
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

def generate_scenes_parallel(scenes):
    """Generate individual scene video files in parallel for better performance."""
    scene_files = []
    try:
        # Use ThreadPoolExecutor for parallel FFmpeg execution
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit all scene generation tasks
            future_to_index = {
                executor.submit(create_scene, text, f"scene_{i}.mp4"): i 
                for i, text in enumerate(scenes[:5])
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    future.result()  # Will raise exception if scene creation failed
                    scene_files.append(f"scene_{index}.mp4")
                    print(f"✓ Scene {index} completed")
                except Exception as e:
                    print(f"✗ Scene {index} failed: {e}")
                    raise  # Re-raise to stop processing
        
        print(f"\n🚀 Generated {len(scene_files)} scenes in parallel")
        return sorted(scene_files)  # Sort to maintain order
    except Exception as e:
        print(f"❌ Error in parallel scene generation: {e}")
        return None

def generate_scenes(scenes):
    """Generate individual scene video files (fallback to sequential if parallel fails)."""
    print(f"\n🎬 Generating {len(scenes[:5])} video scenes...")
    
    # Try parallel generation first
    result = generate_scenes_parallel(scenes)
    if result:
        return result
    
    # Fallback to sequential generation
    print("⚠️ Parallel generation failed, falling back to sequential...")
    scene_files = []
    try:
        for i, text in enumerate(scenes[:5]):
            filename = f"scene_{i}.mp4"
            create_scene(text, filename)
            scene_files.append(filename)
        
        print(f"✅ Generated {len(scene_files)} scenes (sequential)")
        return scene_files
    except Exception as e:
        print(f"❌ Error generating scenes: {e}")
        return None

def combine_scenes(scene_files):
    """Combine scene files into final video."""
    try:
        # Create file list for ffmpeg
        with open(FILE_LIST_FILE, "w") as f:
            for file in scene_files:
                f.write(f"file '{file}'\n")

        # Generate output filename
        output_filename = os.path.join(OUTPUT_FOLDER, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        print(f"\n🎥 Merging scenes into: {output_filename}")
        
        # Combine videos
        result = subprocess.run([
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", FILE_LIST_FILE,
            "-i", "audio.mp3",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-af", "apad",
            "-shortest",
            "-y",
            output_filename
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print("FFmpeg error during concat:")
            print(result.stderr.decode())
            return None

        print("Video generated successfully!")
        return output_filename
    except Exception as e:
        print(f"Error combining scenes: {e}")
        return None

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
    with video_generation_context() as temp_files:
        try:
            # Generate individual scenes
            scene_files = generate_scenes(scenes)
            if scene_files:
                temp_files.extend(scene_files)  # Track for cleanup
            
            if not scene_files:
                # Reset status on failure
                try:
                    sheet.update_cell(row_index, status_col, "")
                    print("🔄 Status reset due to scene generation failure")
                except:
                    pass
                return
            
            # Combine into final video
            output_filename = combine_scenes(scene_files)
            if not output_filename:
                # Reset status on failure
                try:
                    sheet.update_cell(row_index, status_col, "")
                    print("🔄 Status reset due to video combination failure")
                except:
                    pass
                return
            
            # Upload and update status
            upload_success = upload_and_update_status(output_filename, scenes, row_index, sheet)
            
            if upload_success:
                print("🎉 Video processing completed successfully!")
            else:
                print("⚠️ Video generated but upload failed. Check quota limits.")
                
        except Exception as e:
            print(f"💥 Unexpected error during processing: {e}")
            # Reset status on unexpected error
            try:
                sheet.update_cell(row_index, status_col, "")
                print("🔄 Status reset due to unexpected error")
            except:
                pass

if __name__ == "__main__":
    main()