import os
import logging
import chardet
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ===================== 配置项 =====================
API_BASE_URL = "https://book.13ehappy.com/api"
TOKEN_ID = "P5zM1wpxnq1byHmL7pAnr9Foo7XCuQr9"
TOKEN_SECRET = "2wOrw6iSaQ458hAaCqA60w6OlABatSqd"
BOOK_NAME = "CHM电子书导入"
HTML_DIR = "./docs"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
LOG_FILE = "bookstack_import.log"
# ==================================================

# 日志初始化
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建请求会话
def init_session():
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Token {TOKEN_ID}:{TOKEN_SECRET}",
        "Accept": "application/json"
    })
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session

# 自动获取或创建书本
def get_or_create_book(session: requests.Session, book_name: str) -> int | None:
    try:
        res = session.get(f"{API_BASE_URL}/books", timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        books = res.json()

        for book in books:
            if book["name"].strip() == book_name.strip():
                book_id = book["id"]
                logger.info(f"书本已存在：{book_name} (ID={book_id})")
                return book_id

        logger.info(f"书本不存在，正在创建：{book_name}")
        create_res = session.post(
            f"{API_BASE_URL}/books",
            json={"name": book_name, "description": "CHM电子书自动导入"},
            timeout=REQUEST_TIMEOUT
        )
        create_res.raise_for_status()
        new_book = create_res.json()
        book_id = new_book["id"]
        logger.info(f"书本创建成功：{book_name} (ID={book_id})")
        return book_id

    except Exception as e:
        logger.error(f"获取/创建书本失败：{str(e)}")
        return None

# 读取 HTML 文件（自动编码）
def read_html_file(file_path: Path) -> str:
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        detect = chardet.detect(raw)
        encoding = detect.get("encoding", "utf-8")
        if encoding is None:
            encoding = "utf-8"
        encoding = encoding.lower()
        mapping = {"gb2312": "gbk", "windows-1252": "gbk", "iso-8859-1": "gbk"}
        encoding = mapping.get(encoding, encoding)
        return raw.decode(encoding, errors="ignore")
    except Exception as e:
        logger.warning(f"读取失败：{file_path} {str(e)}")
        return ""

# 上传图片到 BookStack
def upload_image(session: requests.Session, img_path: Path) -> str | None:
    if not img_path.exists() or not img_path.is_file():
        return None
    allow = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    if img_path.suffix.lower() not in allow:
        return None
    try:
        with open(img_path, "rb") as f:
            r = session.post(
                f"{API_BASE_URL}/images",
                files={"image": (img_path.name, f), "type": (None, "gallery")},
                timeout=REQUEST_TIMEOUT
            )
        r.raise_for_status()
        return r.json().get("url")
    except Exception:
        return None

# 清理 HTML
def clean_html(soup: BeautifulSoup):
    body = soup.find("body")
    if body is None:
        return soup.new_tag("body")

    for tag in ["script", "style", "iframe", "noscript", "meta", "link"]:
        for elem in body.find_all(tag):
            elem.decompose()

    for dtree in body.find_all(class_=lambda c: c is not None and "dtree" in c.lower()):
        dtree.decompose()
    return body

# 处理单个 HTML
def process_file(session: requests.Session, file_path: Path, book_id: int):
    logger.info(f"处理：{file_path}")
    html = read_html_file(file_path)
    if not html:
        return

    try:
        soup = BeautifulSoup(html, "html.parser")
    except:
        return

    # 标题
    title_tag = soup.find("title")
    name = title_tag.get_text(strip=True) if title_tag else file_path.stem
    name = name[:255]

    # 清理内容
    body = clean_html(soup)

    # 替换图片
    for img in body.find_all("img"):
        src = img.get("src", "")
        if src.startswith(("http://", "https://", "data:")):
            continue
        img_path = (file_path.parent / src).resolve()
        new_url = upload_image(session, img_path)
        if new_url:
            img["src"] = new_url

    # 创建页面
    try:
        r = session.post(
            f"{API_BASE_URL}/pages",
            json={"book_id": book_id, "name": name, "html": str(body)},
            timeout=REQUEST_TIMEOUT
        )
        r.raise_for_status()
        logger.info(f"✅ 导入成功：{name}")
    except Exception as e:
        logger.error(f"❌ 导入失败：{name} {str(e)}")

# 主程序
def main():
    session = init_session()
    book_id = get_or_create_book(session, BOOK_NAME)
    if not book_id:
        logger.error("无法获取或创建书本，退出")
        return

    root = Path(HTML_DIR)
    if not root.exists():
        logger.error(f"目录不存在：{HTML_DIR}")
        return

    files = list(root.rglob("*.html")) + list(root.rglob("*.htm"))
    logger.info(f"共找到 {len(files)} 个 HTML 文件")

    for i, f in enumerate(files, 1):
        logger.info(f"进度 {i}/{len(files)}")
        process_file(session, f, book_id)

    logger.info("✅ 全部导入完成！")

if __name__ == "__main__":
    main()