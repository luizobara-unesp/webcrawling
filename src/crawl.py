import os
import logging
import time
from datetime import datetime, UTC
from collections import deque
from urllib.parse import urlparse
import sys 

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from db import engine 
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import table, column

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
logging.getLogger('WDM').setLevel(logging.WARNING)

FIXED_SLEEP_AFTER_LOAD = 2 
DB_UPSERT_BATCH_SIZE = 1000

def format_elapsed_time(seconds):
    """Converte segundos para um formato H:M:S (ex: 1h 5m 30s)"""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}h {minutes}m {seconds}s"

def setup_driver():
    """Inicializa o WebDriver usando webdriver-manager."""
    logging.debug("Setting up Chrome driver (headless mode) using webdriver-manager...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--log-level=3')

    try:
        os.environ['WDM_LOG_LEVEL'] = '3' 
        log_path = getattr(os, 'devnull', 'nul')
        service = Service(ChromeDriverManager().install(), log_path=log_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.debug("Driver setup complete.")
        return driver
    except Exception as e:
        logging.error(f"!!! Error initializing WebDriver: {e}", exc_info=True)
        return None

def generate_id_from_url(url_path):
    """Gera ID único a partir do path da URL."""
    try:
        clean_path = url_path.strip("/").replace("/", "_")
        if not clean_path:
            return "homepage"
        max_len = 250
        if len(clean_path) > max_len:
            logging.warning(f"Generated ID exceeds max length ({max_len}): {clean_path[:max_len]}...")
            return clean_path[:max_len]
        return clean_path
    except Exception as e:
        fallback_id = "unknown_" + str(int(datetime.now(UTC).timestamp()))
        logging.warning(f"Error generating ID for path '{url_path}': {e}. Using fallback: {fallback_id}")
        return fallback_id

def crawl_site(start_url):
    """Varre o site para descobrir URLs #!/, usando pausa fixa."""
    logging.info("Initializing WebDriver...")
    driver = setup_driver()
    if not driver:
        logging.error("Driver not initialized. Crawl aborted.")
        return []
    
    logging.info("WebDriver initialized. Starting crawl loop...")
    
    try:
        parsed_start_url = urlparse(start_url)
        base_url = f"{parsed_start_url.scheme}://{parsed_start_url.netloc}"
        link_pattern = base_url + "/#!/"
    except Exception as e:
        logging.error(f"Invalid start_url '{start_url}': {e}", exc_info=True)
        if driver: driver.quit()
        return []

    BLOCK_PATTERNS = (
        "/noticia/",
        "/noticias/",
        "/sobre-o-campus",
        "/graduacao/engenharia-de-controle-e-automacao/apresentacao",
        "/pos-graduacao/pos-ca/eventos"
    )

    visited_urls = set()
    pages_to_visit = deque([start_url])
    final_pages_dict = {}

    crawl_start_time = time.time()
    page_count = 0

    while pages_to_visit:
        current_url = pages_to_visit.popleft()
        current_url_clean = current_url.rstrip("/")

        if current_url_clean in visited_urls:
            continue

        is_url_blocked = any(pattern in current_url_clean for pattern in BLOCK_PATTERNS)
        if is_url_blocked:
            logging.debug(f"Skipping blocked URL: {current_url_clean}")
            continue

        visited_urls.add(current_url_clean)
        page_count += 1
        
        elapsed_total_seconds = time.time() - crawl_start_time
        time_str = format_elapsed_time(elapsed_total_seconds)
        
        total_found = page_count + len(pages_to_visit)
        
        status_line = f"[{time_str}] [{page_count} visitadas / {len(pages_to_visit)} na fila / {total_found} urls encontradas]" # -> {current_url_clean}
        
        print(status_line.ljust(150), end='\r') 
        sys.stdout.flush()

        try:
            driver.get(current_url_clean)
            time.sleep(FIXED_SLEEP_AFTER_LOAD)

            try:
                if "#!/" in current_url_clean:
                    url_path = current_url_clean.split("#!/")[1]
                    if url_path:
                        page_id = generate_id_from_url(url_path)
                        if page_id not in final_pages_dict:
                            final_pages_dict[page_id] = {"id": page_id, "url": current_url_clean}
            except IndexError:
                if current_url_clean != start_url.rstrip('/'):
                    print() 
                    logging.warning(f"Could not extract path from non-root URL: {current_url_clean}")
            except Exception as e:
                print() 
                logging.error(f"Error processing URL {current_url_clean} for final list: {e}")

            hrefs = []
            try:
                links_elements = driver.find_elements(By.TAG_NAME, "a") 
                hrefs = [link.get_attribute("href") for link in links_elements if link.get_attribute("href")]
            except StaleElementReferenceException:
                print() 
                logging.warning(f" -> Stale elements while finding links on {current_url_clean}. Might miss some links.")
            except Exception as e:
                print() 
                logging.error(f" -> Error finding/reading links on {current_url_clean}: {e.__class__.__name__}")

            for href in hrefs:
                try:
                    if not isinstance(href, str):
                        continue 

                    href_clean = href.strip().rstrip("/")
                    
                    is_blocked = any(pattern in href_clean for pattern in BLOCK_PATTERNS)
                    
                    if href_clean.startswith(link_pattern) and \
                       href_clean not in visited_urls and \
                       href_clean not in pages_to_visit and \
                       not is_blocked:
                        
                        pages_to_visit.append(href_clean)
                        
                except AttributeError: 
                    continue 
                except Exception as e:
                    print() 
                    logging.error(f" -> Error processing href '{href}': {e}")
            
        except WebDriverException as e:
            print() 
            logging.error(f" -> WebDriverException on {current_url_clean}: {e.msg.splitlines()[0] if e.msg else e.__class__.__name__}. Skipping page.")
        except Exception as e:
            print() 
            logging.error(f" -> Unexpected error on {current_url_clean}: {e}", exc_info=True)

    print(" " * 150, end='\r')
    print() 

    crawl_end_time = time.time()
    total_time = crawl_end_time - crawl_start_time
    logging.info(f"Crawl loop finished visiting {page_count} pages in {total_time:.2f} seconds.")

    if driver:
        driver.quit()
        logging.debug("WebDriver closed.")

    final_pages_list = list(final_pages_dict.values())
    logging.info(f"Discovered {len(final_pages_list)} unique pages based on generated ID.")
    return final_pages_list


def upsert_pages_to_db(pages_list):
    """Salva a lista de páginas no banco de dados (UPSERT)."""
    if not pages_list:
        logging.info("No pages found by crawler to upsert.")
        return

    if not engine:
        logging.error("Database engine not initialized. Cannot upsert.")
        return

    valid_pages_list = [p for p in pages_list if p.get("id") and p.get("url")]
    if len(valid_pages_list) < len(pages_list):
        logging.warning(f"Filtered out {len(pages_list) - len(valid_pages_list)} invalid page entries (missing id or url).")

    if not valid_pages_list:
        logging.warning("No valid page data dictionaries remaining after filtering. Nothing to upsert.")
        return

    logging.info(f"Preparing to upsert {len(valid_pages_list)} pages to database...")

    pages_table = table("pages",
        column("id"),
        column("url"),
        column("last_crawled_at")
    )

    now_timestamp = datetime.now(UTC)
    data_to_upsert = [
        {"id": p["id"], "url": p["url"], "last_crawled_at": now_timestamp}
        for p in valid_pages_list
    ]

    total_processed = 0
    for i in range(0, len(data_to_upsert), DB_UPSERT_BATCH_SIZE):
        batch = data_to_upsert[i : i + DB_UPSERT_BATCH_SIZE]
        batch_num = (i // DB_UPSERT_BATCH_SIZE) + 1
        logging.info(f"Upserting batch {batch_num} ({len(batch)} pages)...")

        try:
            stmt = pg_insert(pages_table).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={'url': stmt.excluded.url, 'last_crawled_at': stmt.excluded.last_crawled_at} 
            )

            with engine.begin() as conn:
                result = conn.execute(stmt)
                logging.debug(f"Batch {batch_num} executed. DBAPI rowcount: {result.rowcount}")

            total_processed += len(batch)

        except Exception as e:
            logging.error(f"Error upserting batch {batch_num} to database: {e}", exc_info=True)

    logging.info(f"Successfully executed upsert operations for approximately {total_processed} pages.")


if __name__ == "__main__":
    root_url = "https://www.sorocaba.unesp.br/#!/"

    logging.info("--- Starting site crawl (Discovery Mode - Fixed Sleep) ---")
    start_time = time.time()
    all_pages = crawl_site(root_url)
    end_time = time.time()

    logging.info(f"\n--- CRAWL COMPLETE --- Discovered {len(all_pages)} unique URLs in {end_time - start_time:.2f} seconds.")

    if all_pages:
        upsert_pages_to_db(all_pages)
    else:
        logging.warning("--- No pages discovered. Skipping database upsert. ---")

    logging.info("--- Process Finished ---")