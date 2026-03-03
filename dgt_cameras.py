import requests
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

def get_dgt_cams():
    urls_to_check = [
        "https://www.dgt.es/conoce-el-estado-del-trafico/camaras-de-trafico/?pag=1&prov=28&carr=A-6",
        "https://www.dgt.es/conoce-el-estado-del-trafico/camaras-de-trafico/?pag=2&prov=28&carr=A-6"
    ]
    cam_urls = []
    
    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            
            for url in urls_to_check:
                page.goto(url, timeout=60000)
                page.wait_for_timeout(5000) # wait for dynamic loading
                imgs = page.locator("img").all()
                
                for img in imgs:
                    src = img.get_attribute("src")
                    if src and ("camara" in src.lower() or "infocar" in src.lower()):
                        cam_urls.append(src)
            
            browser.close()
            return cam_urls
    except Exception as e:
        print(f"Error fetching camera urls: {e}")
        return []

def create_collage(urls, output_path="dgt_collage.jpg"):
    if not urls:
        return False
        
    images = []
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                img.thumbnail((300, 300)) # resize to uniform max bounds
                images.append(img)
        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            
    if not images:
        return False
        
    # calculate grid size
    import math
    n = len(images)
    cols = 3
    rows = math.ceil(n / cols)
    
    # assuming uniform size based on first image after thumbnailing
    w, h = images[0].size
    
    collage = Image.new('RGB', (cols * w, rows * h), color='white')
    
    for i, img in enumerate(images):
        col = i % cols
        row = i // cols
        collage.paste(img, (col * w, row * h))
        
    collage.save(output_path)
    return True

if __name__ == "__main__":
    urls = get_dgt_cams()
    if urls:
        print(f"Found {len(urls)} cameras. Creating collage...")
        if create_collage(urls):
            print("Collage created successfully.")
        else:
            print("Failed to create collage.")
    else:
        print("No camera URLs found.")
