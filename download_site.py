import os
import re
import urllib.request
import urllib.parse

BASE_URL = "https://zvb.bg"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

pages = {
    "index.html": "/",
    "about-us.html": "/about-us",
    "services.html": "/services",
    "gallery.html": "/gallery",
    "request-form.html": "/request-form"
}

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

downloaded_assets = set()

def download_file(rel_path):
    if rel_path in downloaded_assets:
        return
    url = urllib.parse.urljoin(BASE_URL, rel_path)
    clean_path = rel_path.lstrip("/").split("?")[0]
    dirname = os.path.dirname(clean_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    
    print(f"Downloading asset: {url} -> {clean_path}")
    data = fetch_url(url)
    if data:
        with open(clean_path, "wb") as f:
            f.write(data)
        downloaded_assets.add(rel_path)

# 1. Download pages and collect asset references
all_assets = set()
page_contents = {}

for filename, path in pages.items():
    print(f"Fetching page: {path}...")
    content = fetch_url(urllib.parse.urljoin(BASE_URL, path))
    if content:
        text = content.decode("utf-8", errors="ignore")
        page_contents[filename] = text
        
        # Find CSS, JS, images, icons
        found = re.findall(r'(?:href|src)=["\'](/[^"\']+\.(?:css|js|png|jpg|jpeg|svg|webp|ico|woff|woff2|ttf))["\']', text)
        for item in found:
            all_assets.add(item)

print(f"Total assets found: {len(all_assets)}")

# Download all assets
for asset in all_assets:
    download_file(asset)

# Also check for css @import or url(...) references inside downloaded css files
css_files = [f for f in downloaded_assets if f.endswith(".css")]
for css_rel in css_files:
    clean_css_path = css_rel.lstrip("/").split("?")[0]
    if os.path.exists(clean_css_path):
        with open(clean_css_path, "r", encoding="utf-8", errors="ignore") as f:
            css_text = f.read()
        css_assets = re.findall(r'url\(["\']?(/[^"\'\)]+)["\']?\)', css_text)
        for ca in css_assets:
            download_file(ca)

# Save pages with local link adjustments
for filename, text in page_contents.items():
    # Replace internal links
    text = text.replace('href="/"', 'href="index.html"')
    text = text.replace('href="/about-us"', 'href="about-us.html"')
    text = text.replace('href="/services"', 'href="services.html"')
    text = text.replace('href="/gallery"', 'href="gallery.html"')
    text = text.replace('href="/request-form"', 'href="request-form.html"')
    text = text.replace('href="/#contact"', 'href="index.html#contact"')
    
    # Replace root-relative asset paths to relative paths
    text = re.sub(r'(href|src)=["\']/(_astro/[^"\']+)["\']', r'\1="\2"', text)
    text = re.sub(r'(href|src)=["\']/(media/[^"\']+)["\']', r'\1="\2"', text)
    text = re.sub(r'(href|src)=["\']/favicon.ico["\']', r'\1="favicon.ico"', text)
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Saved {filename}")

if os.path.exists("zvb_raw.html"):
    os.remove("zvb_raw.html")

print("Finished successfully!")
