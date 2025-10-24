import logging
from datetime import datetime
from collections import deque
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

from db import engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import table, column

DEFAULT_WAIT_TIME = 5
DB_UPSERT_BATCH_SIZE = 1000

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def setup_driver():
    """
    Inicializa e retorna uma instância do Selenium WebDriver.
    Usa webdriver-manager para baixar e gerenciar o chromedriver automaticamente.
    """
    logging.info("Setting up Chrome driver (headless mode) using webdriver-manager...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("Driver setup complete.")
        return driver
    except Exception as e:
        logging.error(f"!!! Error initializing WebDriver: {e}", exc_info=True)
        logging.error("!!! Ensure Chrome is installed.")
        return None

def generate_id_from_url(url_path):
    """
    Gera um ID único a partir do path da URL, substituindo '/' por '_'.
    
    Ex: 'sobre-o-campus/administracao/' -> 'sobre-o-campus_administracao'
    
    Args:
        url_path (str): O caminho da URL (a parte após o '#!/').

    Returns:
        str: Um ID formatado.
    """
    try:
        clean_path = url_path.strip("/").replace("/", "_")
        
        if not clean_path:
            return "homepage"
            
        return clean_path
    except Exception as e:
        logging.warning(f"Error generating ID for path '{url_path}': {e}", exc_info=True)
        return "unknown_" + str(int(datetime.now().timestamp()))

def crawl_site(start_url):
    """
    Varre o site a partir da URL inicial em busca de todas as sub-páginas
    que usam o padrão '#!/'. Retorna uma lista de dicts.
    
    Usa um algoritmo de Busca em Largura (BFS) para navegar.

    Args:
        start_url (str): A URL raiz para iniciar o crawling (ex: "https://site.com/#!/").

    Returns:
        list: Uma lista de dicionários, onde cada dict contém {"id": str, "url": str}.
    """
    driver = setup_driver()
    if not driver:
        logging.error("Driver not initialized. Crawl aborted.")
        return []
        
    wait = WebDriverWait(driver, DEFAULT_WAIT_TIME)
    
    try:
        parsed_start_url = urlparse(start_url)
        base_url = f"{parsed_start_url.scheme}://{parsed_start_url.netloc}"
        link_selector = f"a[href^='{base_url}/#!/']"
    except Exception as e:
        logging.error(f"Invalid start_url '{start_url}': {e}", exc_info=True)
        return []

    visited_urls = set()
    pages_to_visit = deque([start_url])
    final_pages = []

    while pages_to_visit:
        current_url = pages_to_visit.popleft()
        current_url = current_url.rstrip("/")
        
        if current_url in visited_urls:
            continue
            
        visited_urls.add(current_url)
        
        try:
            logging.info(f"Visiting: {current_url}")
            driver.get(current_url)
            
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, link_selector)))
            
            try:
                url_path = current_url.split("#!/")[1]
                
                if url_path:
                    page_id = generate_id_from_url(url_path)
                    final_pages.append({"id": page_id, "url": current_url})
                
            except IndexError:
                pass

            links = driver.find_elements(By.CSS_SELECTOR, link_selector)

            for link in links:
                href = link.get_attribute("href")
                
                if not href:
                    continue
                
                href = href.rstrip("/") 
                
                if href not in visited_urls and href not in pages_to_visit:
                    logging.info(f"  -> Found new page: {href}")
                    pages_to_visit.append(href)

        except (TimeoutException, StaleElementReferenceException) as e:
            logging.warning(f"  -> Error loading page {current_url}: {e.__class__.__name__}")
        except Exception as e:
            logging.error(f"  -> Unexpected error on {current_url}: {e}", exc_info=True)
            
    driver.quit()
    return final_pages

def upsert_pages_to_db(pages_list):
    """
    Salva a lista de páginas no banco de dados (tabela 'pages') em lotes.
    
    Usa 'ON CONFLICT' (UPSERT):
    - Insere novas páginas.
    - Atualiza 'last_crawled_at' de páginas existentes.
    """
    if not pages_list:
        logging.info("No pages found to upsert.")
        return
        
    if not engine:
        logging.error("Database engine not initialized. Exiting.")
        return

    logging.info(f"Preparing to upsert {len(pages_list)} pages to database...")

    pages_table = table("pages",
        column("id"),
        column("url"),
        column("last_crawled_at")
    )
    
    now_timestamp = datetime.utcnow()
    data_to_upsert = [
        {"id": p["id"], "url": p["url"], "last_crawled_at": now_timestamp}
        for p in pages_list
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
                set_={'last_crawled_at': stmt.excluded.last_crawled_at}
            )
            
            with engine.begin() as conn:
                conn.execute(stmt)
                
            total_processed += len(batch)

        except Exception as e:
            logging.error(f"Error upserting batch {batch_num} to database: {e}", exc_info=True)

    logging.info(f"Successfully upserted/updated {total_processed} of {len(pages_list)} pages.")

if __name__ == "__main__":
    root_url = "https://www.sorocaba.unesp.br/#!/"
    
    logging.info("--- Starting site crawl ---")
    all_pages = crawl_site(root_url)
    
    logging.info(f"\n--- CRAWL COMPLETE: Found {len(all_pages)} pages ---")
    
    upsert_pages_to_db(all_pages)
    
    logging.info("--- Process Finished ---")