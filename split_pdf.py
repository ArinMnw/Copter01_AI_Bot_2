import os
import sys
from PyPDF2 import PdfReader, PdfWriter

def split_pdf_by_size(input_pdf, max_size_mb=18):
    if not os.path.exists(input_pdf):
        print(f"File not found: {input_pdf}")
        return
    
    file_size_mb = os.path.getsize(input_pdf) / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        print(f"File {input_pdf} is already under {max_size_mb} MB ({file_size_mb:.2f} MB).")
        return [input_pdf]

    print(f"Splitting {input_pdf} ({file_size_mb:.2f} MB)...")
    reader = PdfReader(input_pdf)
    total_pages = len(reader.pages)
    
    # Estimate pages per chunk
    estimated_pages_per_chunk = max(1, int(total_pages / (file_size_mb / max_size_mb)))
    print(f"Total pages: {total_pages}, Estimated pages per chunk: {estimated_pages_per_chunk}")

    chunks = []
    current_chunk = 1
    start_page = 0

    while start_page < total_pages:
        writer = PdfWriter()
        end_page = min(start_page + estimated_pages_per_chunk, total_pages)
        
        for i in range(start_page, end_page):
            writer.add_page(reader.pages[i])
        
        base_name, ext = os.path.splitext(input_pdf)
        output_filename = f"{base_name}_part{current_chunk}{ext}"
        
        with open(output_filename, "wb") as f_out:
            writer.write(f_out)
        
        chunks.append(output_filename)
        print(f"Created {output_filename} ({os.path.getsize(output_filename) / (1024*1024):.2f} MB)")
        
        start_page = end_page
        current_chunk += 1

    return chunks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_pdf.py <file1> <file2> ...")
        sys.exit(1)
    
    for f in sys.argv[1:]:
        split_pdf_by_size(f)
