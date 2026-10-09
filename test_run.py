import os
import subprocess
import time
from PIL import Image, ImageDraw, ImageFont

from main import (
    IMAGE_FOLDERS,
    AUDIO_FOLDER,
    FONT_PATH,
    OUTPUT_FOLDER,
    SHORTS_AUDIO,
    create_full_video,
    get_ffmpeg_executable,
    setup,
    video_generation_context,
)

# Test input (as provided)
RAW = (
    "You almost missed it\\nbut look at you now|That prayer felt forgotten\\nbut you kept believing|"
    "God was working quietly\\nwhile you were waiting|Jesus saw every tear\\nand strengthened your heart|"
    "Your waiting wasn't wasted#faith,jesus,hope,trustgod,growth+“Be joyful in hope, patient in affliction, faithful in prayer.” - Romans 12:12"
)

def ensure_dirs():
    # Create image folders if missing
    for f in IMAGE_FOLDERS:
        if not os.path.exists(f):
            os.makedirs(f)

    os.makedirs(AUDIO_FOLDER, exist_ok=True)

    if not os.path.exists('test_output'):
        os.makedirs('test_output')


def create_sample_images():
    # For any folder without images, create a simple placeholder image
    for i, folder in enumerate(IMAGE_FOLDERS):
        files = [p for p in os.listdir(folder) if p.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        if files:
            continue

        img_path = os.path.join(folder, f"sample_{i+1}.png")
        img = Image.new('RGB', (1080, 1920), color=(30 + i*30, 60 + i*20, 90 + i*10))
        draw = ImageDraw.Draw(img)
        try:
            if os.path.exists(FONT_PATH):
                font = ImageFont.truetype(FONT_PATH, 80)
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        text = os.path.basename(folder)
        w, h = draw.textsize(text, font=font)
        draw.text(((1080 - w) / 2, (1920 - h) / 2), text, font=font, fill=(255,255,255))
        img.save(img_path)


def make_silent_audio(duration_s=16):
    # Create a silent audio file for the Shorts test
    if os.path.exists(SHORTS_AUDIO):
        return
    cmd = [
        get_ffmpeg_executable(), '-y', '-f', 'lavfi', '-i',
        'anullsrc=r=44100:cl=stereo', '-t', str(duration_s),
        '-q:a', '9', '-acodec', 'libmp3lame', SHORTS_AUDIO,
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def parse_raw(raw):
    left, rest = raw.split('#', 1)
    hashtags, bibleverse = rest.split('+', 1)
    scenes = [s.replace('\\n', '\n') for s in left.split('|')]
    # Ensure 5 scenes
    while len(scenes) < 5:
        scenes.append('')
    return scenes[:5], hashtags, bibleverse


def run_test():
    ensure_dirs()
    create_sample_images()
    make_silent_audio()

    scenes, hashtags, bibleverse = parse_raw(RAW)

    # Ensure output folder
    setup()

    output = os.path.join('test_output', f"test_output_{int(time.time())}.mp4")

    print('Generating test video to', output)
    with video_generation_context() as temp_files:
        create_full_video(scenes, output, 'shorts', temp_files=temp_files)

    if os.path.exists(output):
        print('Test video generated:', output)
    else:
        print('Failed to generate test video')


if __name__ == '__main__':
    run_test()
