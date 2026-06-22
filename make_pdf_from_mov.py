import os
import sys
from moviepy import VideoFileClip
from PIL import Image

def convert_to_pdf(input_file):
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return
        
    clip = VideoFileClip(input_file)
    duration = clip.duration
    print(f"Duration: {duration}s")
    
    images = []
    # Extract 1 frame every 30 seconds
    for t in range(0, int(duration), 30):
        print(f"Extracting frame at {t}s")
        frame = clip.get_frame(t)
        # Convert numpy array to PIL Image
        img = Image.fromarray(frame)
        images.append(img)
    
    if images:
        out_name = input_file + ".pdf"
        images[0].save(out_name, save_all=True, append_images=images[1:], resolution=100.0)
        print(f"Saved PDF to {out_name}")
    else:
        print("No frames extracted.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_pdf_from_mov.py <input_video>")
    else:
        convert_to_pdf(sys.argv[1])
