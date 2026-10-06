"""Optional bounded DailyMed photo cache. Images never identify inventory."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .catalog import identifier

HOST = "dailymed.nlm.nih.gov"


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != "https" or urlparse(newurl).hostname != HOST:
            raise ValueError("The photo source redirected outside DailyMed.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PackagePhotos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.url = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.depth or "drug-photos" in attrs.get("class", "").split():
                self.depth += 1
        if self.depth and tag == "img" and not self.url:
            self.url = attrs.get("src")

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1


def cached(directory, code):
    directory = Path(directory)
    key = identifier(code)
    found = next((directory / f"{key}{ext}" for ext in (".jpg", ".png", ".gif") if (directory / f"{key}{ext}").is_file()), None)
    if found or not directory.is_dir():
        return found
    # The bundled reference photos keep the label's hyphenated NDC as their file name.
    for path in sorted(directory.iterdir()):
        if path.suffix in (".jpg", ".png", ".gif") and "-" in path.stem and path.is_file():
            try:
                if identifier(path.stem) == key:
                    return path
            except ValueError:
                pass
    return None


def fetch_photo(directory, code, product_code=None):
    key = identifier(code)
    search = "https://" + HOST + "/dailymed/search.cfm?" + urlencode({"labeltype": "all", "query": product_code or code})
    opener = build_opener(OfficialRedirects())
    headers = {"User-Agent": "EPICS-Pharm/combined (package photo lookup)"}
    with opener.open(Request(search, headers=headers), timeout=5) as response:
        page = response.read(2_000_001)
    if len(page) > 2_000_000:
        raise ValueError("DailyMed search response is too large.")
    parser = PackagePhotos()
    parser.feed(page.decode("utf-8", errors="replace"))
    if not parser.url:
        raise ValueError("No package photo is available from DailyMed.")
    url = urljoin(search, parser.url)
    if urlparse(url).scheme != "https" or urlparse(url).hostname != HOST:
        raise ValueError("The package photo must come from DailyMed HTTPS.")
    with opener.open(Request(url, headers=headers), timeout=5) as response:
        content = response.read(5_000_001)
    if len(content) > 5_000_000:
        raise ValueError("The package photo exceeds the size limit.")
    extension = ".jpg" if content.startswith(b"\xff\xd8\xff") else ".png" if content.startswith(b"\x89PNG\r\n\x1a\n") else ".gif" if content.startswith((b"GIF87a", b"GIF89a")) else None
    if not extension:
        raise ValueError("The response is not a supported image.")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (key + extension)
    temporary = path.with_suffix(extension + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return path
