import os
import subprocess
from datetime import datetime

# Configuration constants
FONT_PATH = "font.ttf"
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FONT_SIZE = 80
LINE_SPACING = 12
DEFAULT_DURATION = 3
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

def create_scene(text, output, duration=DEFAULT_DURATION):
    """
    Create a vertical video scene with text overlay on a black background.
    
    Args:
        text: The text to display in the scene
        output: Output video file path
        duration: Duration of the video in seconds (default: 3)
    """
    # Write text to temporary file for ffmpeg processing
    with open(TEMP_TEXT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

    # Build ffmpeg command to create text overlay video
    video_size = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"
    # Main text
    main_text_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"textfile={TEMP_TEXT_FILE}:"
        f"fontcolor=white:"
        f"fontsize={FONT_SIZE}:"
        f"line_spacing={LINE_SPACING}:"
        f"x=(w-text_w)/2:"
        f"y=(h-text_h)/2+{TEXT_Y_OFFSET}"
    )

    # Watermark
    watermark_filter = (
        f"drawtext=fontfile={FONT_PATH}:"
        f"text='{WATERMARK_TEXT}':"
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
    result = subprocess.run(cmd)

    # Verify the scene was created successfully
    if not os.path.exists(output):
        print(f"❌ Failed to create {output}")
        exit()

def get_user_scenes():
    print("\n✍️ Enter your 5 lines for the video:\n")

    prompts = [
        "1. Hook (attention grabber): ",
        "2. Emotion (pain/feeling): ",
        "3. Struggle: ",
        "4. Message / Verse: ",
        "5. Ending (hope/impact): "
    ]

    scenes = []
    for prompt in prompts:
        text = input(prompt)
        text = text.replace("\\n", "\n")
        scenes.append(text)

    return scenes

def main():
    """Generate a vertical video with multiple text scenes and combine them."""
    
    # Create output folder if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    # Define the video script scenes
    scenes = get_user_scenes()
    
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
    subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", FILE_LIST_FILE,
        "-c", "copy",
        output_filename
    ])

    print("✅ Video generated successfully!")

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