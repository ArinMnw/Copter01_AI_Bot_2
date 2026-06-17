import fitz
import os

def split_pdf_by_size(filepath, max_mb=20.0):
    max_bytes = max_mb * 1024 * 1024
    
    print(f"Opening: {filepath}")
    doc = fitz.open(filepath)
    total_pages = doc.page_count
    
    output_dir = os.path.dirname(filepath)
    base_name = os.path.basename(filepath).replace(".pdf", "")
    
    part_num = 1
    start_page = 0
    
    out_doc = fitz.open()
    
    for page_idx in range(total_pages):
        # Create a temporary document just for this page to check its approximate size
        temp_doc = fitz.open()
        temp_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        # We can't know exact size until save, but we can guess it's roughly proportional.
        # However, to be safe, we can just insert into out_doc and check size.
        
        out_doc.insert_pdf(doc, from_page=page_idx, to_page=page_idx)
        
        # Check size every 5 pages to save time, or every page if we want to be exact
        if page_idx % 10 == 0 or page_idx == total_pages - 1:
            # We can't easily check size without saving, let's just do a rough estimate or save to a memory buffer
            # Actually, fitz has write() to bytes
            pdf_bytes = out_doc.write()
            if len(pdf_bytes) > max_bytes and start_page < page_idx:
                # Revert: create a new doc WITHOUT this last batch, save it, and start a new doc
                # But it's easier to just save the document BEFORE this insertion if it exceeds.
                pass
                
    doc.close()

# Let's do a simpler approach: Estimate size per page.
def split_pdf_simple(filepath, max_mb=19.5):
    max_bytes = max_mb * 1024 * 1024
    doc = fitz.open(filepath)
    total_pages = doc.page_count
    file_size = os.path.getsize(filepath)
    
    avg_page_size = file_size / total_pages
    pages_per_chunk = int(max_bytes / avg_page_size)
    # Be conservative
    pages_per_chunk = int(pages_per_chunk * 0.8)
    if pages_per_chunk < 1: pages_per_chunk = 1
    
    print(f"Total pages: {total_pages}, Avg page size: {avg_page_size/1024:.2f} KB")
    print(f"Splitting every {pages_per_chunk} pages to keep under {max_mb} MB")
    
    output_dir = os.path.dirname(filepath)
    base_name = os.path.basename(filepath).replace(".pdf", "")
    
    for i in range(0, total_pages, pages_per_chunk):
        start = i
        end = min(i + pages_per_chunk - 1, total_pages - 1)
        
        out_doc = fitz.open()
        out_doc.insert_pdf(doc, from_page=start, to_page=end)
        
        out_filepath = os.path.join(output_dir, f"{base_name}_part{i//pages_per_chunk + 1}.pdf")
        out_doc.save(out_filepath, garbage=4, deflate=True)
        out_doc.close()
        
        actual_size = os.path.getsize(out_filepath) / (1024*1024)
        print(f"Saved: {out_filepath} - Size: {actual_size:.2f} MB - Pages: {start+1} to {end+1}")
        
    doc.close()
    
if __name__ == "__main__":
    split_pdf_simple(r"C:\Users\Copter\Downloads\อออิน4s\All in 4s Collector’s Edition (2).pdf")
