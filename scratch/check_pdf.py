import fitz
import sys

def check_pdf(filepath):
    try:
        doc = fitz.open(filepath)
        num_pages = doc.page_count
        print(f"Total pages: {num_pages}")
        
        # Extract text from the first 5 pages
        text_found = False
        for i in range(min(5, num_pages)):
            page = doc.load_page(i)
            text = page.get_text()
            if text.strip():
                text_found = True
                print(f"--- Page {i+1} ---")
                print(text[:200] + "..." if len(text) > 200 else text)
                
        if not text_found:
            print("No text found in the first 5 pages. This might be a scanned PDF (images only).")
            
        doc.close()
    except Exception as e:
        print(f"Error reading PDF: {e}")

if __name__ == "__main__":
    filepath = r"C:\Users\Copter\Downloads\อออิน4s\All in 4s Collector’s Edition (2).pdf"
    check_pdf(filepath)
