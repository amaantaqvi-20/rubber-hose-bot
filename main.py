import os
import base64
import pickle
import asyncio
import requests
import random
from groq import Groq
from edge_tts import Communicate
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, VideoFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
YOUTUBE_TOKEN_BASE64 = os.environ.get("YOUTUBE_TOKEN_BASE64")
VOICE = "en-US-SteffanNeural"

# --- 1. THE BRAIN (Groq) ---
def get_script():
    client = Groq(api_key=GROQ_API_KEY)
    history_file = "history.txt"
    
    if not os.path.exists(history_file):
        open(history_file, "w").close()
    
    with open(history_file, "r") as f:
        history = f.read().splitlines()

    system_prompt = "You are a 1930s horror writer. Write one terrifying 12-word sentence for a vintage cartoon. Output ONLY the text."
    
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": "New nightmare idea."}],
        temperature=0.9
    )
    script = completion.choices[0].message.content.strip().replace('"', '')
    
    with open(history_file, "a") as f: f.write(script + "\n")
    return script

# --- 2. THE ARTIST (Pollinations AI) ---
def generate_image(prompt):
    style = " 1930s rubber hose style, black and white, heavy film grain, unsettling, high contrast, scratched texture"
    url = f"https://image.pollinations.ai/prompt/{prompt + style}?width=1080&height=1920&nologo=true"
    r = requests.get(url)
    with open("temp_image.png", "wb") as f: f.write(r.content)
    return "temp_image.png"

# --- 3. THE VOICE (Edge-TTS) ---
async def generate_audio(text):
    communicate = Communicate(text, VOICE, rate="-30%", pitch="-20Hz")
    await communicate.save("temp_audio.mp3")
    return "temp_audio.mp3"

# --- 4. THE VIDEO ENGINE (MoviePy) ---
def create_video(image_path, audio_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration + 2 
    
    img_clip = ImageClip(image_path).set_duration(duration).set_fps(24)
    img_clip = img_clip.set_audio(audio)
    
    # Optional: If you have a 'grain.mp4' file in assets, uncomment below to overlay it
    # grain = VideoFileClip("assets/grain.mp4").loop().set_duration(duration).set_opacity(0.3)
    # final = CompositeVideoClip([img_clip, grain])
    
    output_path = "final_short.mp4"
    img_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    return output_path

# --- 5. THE PUBLISHER (YouTube API) ---
def upload_to_youtube(video_path, script_text):
    # Decode the secret token from GitHub Environment
    creds_data = base64.b64decode(YOUTUBE_TOKEN_BASE64)
    creds = pickle.loads(creds_data)
    
    youtube = build("youtube", "v3", credentials=creds)
    
    request_body = {
        "snippet": {
            "title": f"The Uncanny Archive: {script_text[:50]}...",
            "description": f"{script_text}\n\n#shorts #horror #1930s #creepy",
            "tags": ["horror", "shorts", "1930s", "vintage"],
            "categoryId": "24", # Entertainment
            "defaultLanguage": "en-US",
            "defaultAudioLanguage": "en-US"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
    
    response = request.execute()
    print(f"✅ Video Uploaded! ID: {response['id']}")

# --- MAIN LOOP ---
async def main():
    print("🚀 Starting Bot...")
    script = get_script()
    img = generate_image(script)
    await generate_audio(script)
    video = create_video(img, "temp_audio.mp3")
    
    if YOUTUBE_TOKEN_BASE64:
        upload_to_youtube(video, script)
    else:
        print("⚠️ No YouTube token found. Skipping upload.")

if __name__ == "__main__":
    asyncio.run(main())