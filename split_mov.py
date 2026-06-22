import os
import sys
from moviepy import VideoFileClip
import math

def split_video(input_file, target_size_mb=18):
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
    
    file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB")
    
    clip = VideoFileClip(input_file)
    duration = clip.duration
    
    # Estimate bitrate if possible, or just use ratio
    # If 353MB is total duration, 18MB is 18/353 of duration
    ratio = target_size_mb / file_size_mb
    chunk_duration = duration * ratio
    
    num_chunks = math.ceil(duration / chunk_duration)
    print(f"Duration: {duration}s, splitting into {num_chunks} chunks of {chunk_duration}s")
    
    base_name, ext = os.path.splitext(input_file)
    out_dir = os.path.dirname(input_file)
    
    for i in range(num_chunks):
        start_time = i * chunk_duration
        end_time = min((i + 1) * chunk_duration, duration)
        
        # we will use mp4 extension
        out_name = f"{base_name}_part{i+1}.mp4"
        print(f"Writing {out_name}...")
        
        subclip = clip.subclipped(start_time, end_time)
        subclip.write_videofile(out_name, codec="libx264", audio_codec="aac")
        
        print(f"Saved {out_name}")
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_mov.py <input_video>")
    else:
        split_video(sys.argv[1])
