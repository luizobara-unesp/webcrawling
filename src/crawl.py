import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

from db import engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import table, column

# DRIVER_PATH = r'C:\Users\USER\projects\webcrawling\drivers\chromedriver.exe'

def setup_driver():
    """Inicializa e retorna uma instância do Selenium WebDriver."""
    print("Setting up Chrome driver (headless mode)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

    driver_path_local = os.environ.get('LOCAL_DRIVER_PATH') 
    
    try:
        if driver_path_local:
             print(f"Using local driver path: {driver_path_local}")
             service = Service(executable_path=driver_path_local)
             driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
             print("Using ChromeDriver from PATH (expected in GitHub Actions).")
             driver = webdriver.Chrome(options=chrome_options) 
        
        print("Driver setup complete.")
        return driver
    except Exception as e:
        print(f"!!! Error initializing WebDriver: {e}")
        print("!!! Ensure ChromeDriver is installed and accessible in PATH (Actions) or via LOCAL_DRIVER_PATH (Local).")
        return None

def generate_id_from_url(url_path):
    """
    Gera um ID único a partir do path da URL, substituindo '/' por '_'.
    Ex: 'sobre-o-campus/administracao/' -> 'sobre-o-campus_administracao'
    """
    try:
        clean_path = url_path.strip("/").replace("/", "_")
        
        if not clean_path:
            return "homepage"
            
        return clean_path
    except Exception:
        return "unknown_" + str(int(time.time()))

def crawl_site(start_url):
    """
    Varre o site a partir da URL inicial em busca de todas as sub-páginas
    que usam o padrão '#!/'. Retorna uma lista de dicts.
    """
    driver = setup_driver()
    wait = WebDriverWait(driver, 5) 
    base_url = "https://www.sorocaba.unesp.br/"
    
    visited_urls = set() 
    pages_to_visit = [start_url]
    final_pages = []

    while pages_to_visit:
        current_url = pages_to_visit.pop(0) 
        current_url = current_url.rstrip("/")
        
        if current_url in visited_urls:
            continue
            
        visited_urls.add(current_url)
        
        try:
            print(f"Visiting: {current_url}")
            driver.get(current_url)
            
            wait.until(EC.presence_of_element_located((By.ID, "idCorpoRodape")))
            
            if current_url != start_url:
                try:
                    url_path = current_url.split("#!/")[1]
                    page_id = generate_id_from_url(url_path)
                    final_pages.append({"id": page_id, "url": current_url})
                except IndexError:
                    print(f"  -> Skipping URL with invalid format: {current_url}")

            links = driver.find_elements(By.TAG_NAME, "a")

            for link in links:
                href = link.get_attribute("href")
                
                if not href:
                    continue
                
                href = href.rstrip("/") 
                
                if (href.startswith(base_url + "#!/") and 
                    href not in visited_urls and 
                    href not in pages_to_visit):
                    
                    print(f"  -> Found new page: {href}")
                    pages_to_visit.append(href)

        except (TimeoutException, StaleElementReferenceException) as e:
            print(f"  -> Error loading page {current_url}: {e.__class__.__name__}")
        except Exception as e:
            print(f"  -> Unexpected error on {current_url}: {e}")
            
    driver.quit()
    return final_pages

def upsert_pages_to_db(pages_list):
    """
    Salva a lista de páginas no banco de dados (tabela 'pages').
    Usa 'ON CONFLICT' (UPSERT) para inserir novas páginas ou
    atualizar a data 'last_crawled_at' de páginas existentes.
    """
    if not pages_list:
        print("No pages found to upsert.")
        return
        
    if not engine:
        print("Database engine not initialized. Exiting.")
        return

    print(f"\nUpserting {len(pages_list)} pages to database...")

    pages_table = table("pages",
        column("id"),
        column("url"),
        column("last_crawled_at")
    )

    stmt = pg_insert(pages_table).values(pages_list)

    stmt = stmt.on_conflict_do_update(
        index_elements=['id'], 
        set_={'last_crawled_at': "NOW()"} 
    )
    
    try:
        with engine.begin() as conn:
            conn.execute(stmt)
        print(f"Successfully upserted {len(pages_list)} pages.")
    except Exception as e:
        print(f"Error upserting pages to database: {e}")

if __name__ == "__main__":
    root_url = "https://www.sorocaba.unesp.br/#!/"
    
    print("Starting site crawl...")
    all_pages = crawl_site(root_url)
    
    print("\n--- CRAWL COMPLETE ---")
    
    upsert_pages_to_db(all_pages)