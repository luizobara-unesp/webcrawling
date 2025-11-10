import os
import time
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from db import engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text, table, column

FIXED_SLEEP_SECONDS = 2
DB_UPSERT_BATCH_SIZE = 1000

def setup_driver():
    """Inicializa e retorna uma instância do Selenium WebDriver (versão simplificada para Docker)."""
    print("Setting up Chrome driver (headless mode)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        print("Using ChromeDriver from system PATH.")
        driver = webdriver.Chrome(options=chrome_options) 
        print("Driver setup complete.")
        return driver
    except Exception as e:
        print(f"!!! Error initializing WebDriver: {e}")
        print("!!! Ensure 'chromium-driver' is correctly installed in the Dockerfile.")
        return None
    
def load_pages_from_db():
    """
    Carrega a lista de páginas ativas (is_active = true) da tabela 'pages'.
    Retorna uma lista de dicionários.
    """
    print("Loading pages to scrape from database...")
    if not engine:
        print("Database engine not initialized. Exiting.")
        return []
    pages = []
    try:
        with engine.connect() as conn:
            query = text("SELECT id, url FROM pages WHERE is_active = true")
            result = conn.execute(query)
            for row in result:
                pages.append(row._mapping)
        print(f"Successfully loaded {len(pages)} active pages from database.")
        return pages
    except Exception as e:
        print(f"Error loading pages from database: {e}")
        return []

def get_last_modified_info(driver, url):
    """
    Navega para uma URL, espera o rodapé aparecer, e então força uma 
    pausa fixa para garantir que o JS atualize os dados.
    """
    
    wait_time = 10 
    
    try:
        driver.get(url)

        wait = WebDriverWait(driver, wait_time)
        container_id = "idCorpoRodape"
        date_span_id = "data-atualizacao-pagina"
        user_span_id = "usuario-atualizacao-pagina"
        resp_span_id = "responsavel-pagina"
        
        container = wait.until(
            EC.visibility_of_element_located((By.ID, container_id))
        )

        time.sleep(FIXED_SLEEP_SECONDS)

        container = driver.find_element(By.ID, container_id) 
        full_text = container.text.strip()
        
        try:
            date_time_str = container.find_element(By.ID, date_span_id).text.strip()
            date_str = date_time_str.split(' ')[0] if date_time_str else "Not Found"
        except NoSuchElementException:
            date_str = "Not Found"

        try:
            updated_by_str = container.find_element(By.ID, user_span_id).text.strip()
        except NoSuchElementException:
            updated_by_str = "Not Found"

        try:
            responsible_str = container.find_element(By.ID, resp_span_id).text.strip()
        except NoSuchElementException:
            responsible_str = "Not Found"

        return {
            "full_modified_text": full_text if full_text else "Not Found", 
            "modified_date": date_str,
            "updated_by": updated_by_str if updated_by_str else "Not Found",
            "responsible": responsible_str if responsible_str else "Not Found"
        }

    except (TimeoutException, NoSuchElementException):
        print(f"  -> [AVISO] Página pulada (sem rodapé ou timeout): {url}")
        return None 

    except StaleElementReferenceException:
        print(f"  -> [AVISO] Página pulada (Stale Element): {url}")
        return None

    except Exception as e:
        print(f"  -> [ERRO] Falha em {url}: Erro inesperado: {e.__class__.__name__}")
        return None
            
def save_history_to_db_upsert(history_records):
    """
    Salva os registros de scrape (lista de dicts) na tabela 'scrape_history'
    usando a lógica de UPSERT.
    """
    if not history_records:
        print("No scrape history records to save.")
        return
    if not engine:
        print("Database engine not initialized. Exiting.")
        return

    print(f"\nUpserting {len(history_records)} history records to database...")

    history_table = table("scrape_history",
        column("page_id"), column("scrape_timestamp"), column("modified_date"),
        column("updated_by"), column("responsible"), column("full_modified_text")
    )

    total_processed = 0
    for i in range(0, len(history_records), DB_UPSERT_BATCH_SIZE):
        batch = history_records[i : i + DB_UPSERT_BATCH_SIZE]
        batch_num = (i // DB_UPSERT_BATCH_SIZE) + 1
        print(f"Upserting batch {batch_num} ({len(batch)} records)...")

        try:
            stmt = pg_insert(history_table).values(batch)
            
            stmt = stmt.on_conflict_do_update(
                index_elements=['page_id'],
                
                set_={
                    'scrape_timestamp': stmt.excluded.scrape_timestamp,
                    'modified_date': stmt.excluded.modified_date,
                    'updated_by': stmt.excluded.updated_by,
                    'responsible': stmt.excluded.responsible,
                    'full_modified_text': stmt.excluded.full_modified_text
                }
            )

            with engine.begin() as conn:
                result = conn.execute(stmt)
            
            total_processed += len(batch)

        except Exception as e:
            print(f"Error upserting batch {batch_num} to database: {e}")
            print("!!! VERIFIQUE SE A COLUNA 'page_id' POSSUI UMA RESTRIÇÃO 'UNIQUE' NO BANCO DE DADOS. !!!")

    print(f"Successfully executed upsert operations for {total_processed} records.")

if __name__ == "__main__":
    pages_to_scrape = load_pages_from_db()
    if not pages_to_scrape:
        print("No pages to scrape. Exiting script.")
    else:
        results = []
        driver = setup_driver()
        
        if driver is None:
            print("Driver não foi inicializado. Abortando scrape.")
            exit() 

        current_scrape_timestamp = datetime.now(timezone.utc)
        total_pages = len(pages_to_scrape)
        print(f"\nStarting scrape of {total_pages} pages...")
            
        try:
            for i, page in enumerate(pages_to_scrape):
                page_id = page["id"]
                page_url = page["url"]
                print(f"Carregando... {i + 1}/{total_pages} páginas", end='\r')
                
                info = get_last_modified_info(driver, page_url)
                
                result_data = {
                    "page_id": page_id,
                    "scrape_timestamp": current_scrape_timestamp
                }
                
                if info:
                    result_data.update(info)
                else:
                    result_data.update({
                        "full_modified_text": "Not Found",
                        "modified_date": "Not Found",
                        "updated_by": "Not Found",
                        "responsible": "Not Found"
                    })
                results.append(result_data)
        
        finally:
            print() 
            print("\nScraping complete. Closing driver.")
            if driver: 
                driver.quit()
        
        save_history_to_db_upsert(results)