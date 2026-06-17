import fitz
import os
import glob

def split_large_pdfs(directory, max_mb=19.5):
    max_bytes = max_mb * 1024 * 1024
    
    # Find all PDFs recursively
    pdf_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
                
    for filepath in pdf_files:
        # Skip already split parts to avoid infinite loop
        if "_part" in filepath:
            continue
            
        file_size = os.path.getsize(filepath)
        if file_size > max_bytes:
            print(f"Splitting: {filepath} (Size: {file_size/(1024*1024):.2f} MB)")
            
            try:
                doc = fitz.open(filepath)
                total_pages = doc.page_count
                
                avg_page_size = file_size / total_pages
                pages_per_chunk = int(max_bytes / avg_page_size)
                # Be conservative
                pages_per_chunk = int(pages_per_chunk * 0.8)
                if pages_per_chunk < 1: pages_per_chunk = 1
                
                output_dir = os.path.dirname(filepath)
                base_name = os.path.basename(filepath).replace(".pdf", "")
                
                for i in range(0, total_pages, pages_per_chunk):
                    start = i
                    end = min(i + pages_per_chunk - 1, total_pages - 1)
                    
                    out_doc = fitz.open()
                    out_doc.insert_pdf(doc, from_page=start, to_page=end)
                    
                    out_filepath = os.path.join(output_dir, f"{base_name}_part{i//pages_per_chunk + 1}.pdf")
                    # Only save if it doesn't already exist to save time
                    if not os.path.exists(out_filepath):
                        out_doc.save(out_filepath, garbage=4, deflate=True)
                        actual_size = os.path.getsize(out_filepath) / (1024*1024)
                        print(f"  -> Saved: {out_filepath} ({actual_size:.2f} MB)")
                    else:
                        print(f"  -> Skipped (already exists): {out_filepath}")
                    out_doc.close()
                    
                doc.close()
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

if __name__ == "__main__":
    split_large_pdfs(r"C:\Users\Copter\Downloads\อออิน4s")
