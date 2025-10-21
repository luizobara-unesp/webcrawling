import os
import time
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from db import engine
from sqlalchemy import text, table, column, insert

DRIVER_PATH = r'C:\Users\USER\projects\webcrawling\drivers\chromedriver.exe'

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

def _find_text_or_default(container, by, value, default="Not Found"):
    """
    Função helper para tentar encontrar um elemento e pegar seu texto.
    Se não encontrar (NoSuchElementException), retorna o valor padrão.
    """
    try:
        if not container.is_displayed():
             return default
        text_content = container.find_element(by, value).text
        return text_content if text_content and not text_content.isspace() else default
    except NoSuchElementException:
        return default
    except StaleElementReferenceException:
         return default

def get_last_modified_info(driver, url):
    """
    Navega para uma URL específica e extrai as informações detalhadas de
    modificação. Retorna "Not Found" nos campos ausentes.
    (Adiciona retentativa INTERNA para ler spans após encontrar o container)
    """
    page_load_retries = 3 
    span_read_retries = 3 
    retry_delay = 0.5     

    for attempt in range(page_load_retries):
        try:
            driver.get(url)
            wait = WebDriverWait(driver, 10)
            container_id = "idCorpoRodape"
            date_span_id = "data-atualizacao-pagina"
            user_span_id = "usuario-atualizacao-pagina"
            resp_span_id = "responsavel-pagina"

            container_element = wait.until(EC.presence_of_element_located((By.ID, container_id)))

            for span_attempt in range(span_read_retries):
                try:
                    full_text = container_element.text
                    if not full_text or full_text.isspace():
                         if span_attempt < span_read_retries - 1:
                              time.sleep(retry_delay)
                              container_element = driver.find_element(By.ID, container_id) 
                              continue 
                         else:
                              full_text = "Not Found" 

                    date_time_str = _find_text_or_default(container_element, By.ID, date_span_id)
                    updated_by_str = _find_text_or_default(container_element, By.ID, user_span_id)
                    responsible_str = _find_text_or_default(container_element, By.ID, resp_span_id)

                    if (date_time_str != "Not Found" or
                        updated_by_str != "Not Found" or
                        responsible_str != "Not Found"):

                        date_str = date_time_str.split(' ')[0] if date_time_str != "Not Found" else "Not Found"

                        return {
                            "full_modified_text": full_text if full_text else "Not Found", 
                            "modified_date": date_str,
                            "updated_by": updated_by_str,
                            "responsible": responsible_str
                        }
                    elif span_attempt < span_read_retries - 1:
                        time.sleep(retry_delay)
                        container_element = driver.find_element(By.ID, container_id) 
                    else:
                         return {
                            "full_modified_text": "Not Found",
                            "modified_date": "Not Found",
                            "updated_by": "Not Found",
                            "responsible": "Not Found"
                         }
                except StaleElementReferenceException:
                     if span_attempt < span_read_retries - 1:
                          print()
                          print(f"  -> [AVISO] StaleElement (interno) em {url}. Tentando re-localizar ({span_attempt + 1}/{span_read_retries})...")
                          time.sleep(0.5)
                          try:
                              container_element = driver.find_element(By.ID, container_id)
                          except NoSuchElementException:
                               print()
                               print(f"  -> [ERRO] Container sumiu durante retentativa interna em {url}.")
                               return None 
                     else:
                          print()
                          print(f"  -> [ERRO] Falha interna em {url} após {span_read_retries} tentativas (StaleElement).")
                          return None 

        except StaleElementReferenceException: 
            if attempt < page_load_retries - 1:
                print()
                print(f"  -> [AVISO] StaleElement (carregamento) em {url}. Tentando novamente ({attempt + 1}/{page_load_retries})...")
                time.sleep(1) 
            else:
                print()
                print(f"  -> [ERRO] Falha em {url} após {page_load_retries} tentativas (StaleElement).")
                return None
        except TimeoutException:
            print()
            print(f"  -> [ERRO] Falha em {url}: Elemento '{container_id}' não encontrado (Timeout).")
            return None 
        except Exception as e:
            print()
            print(f"  -> [ERRO] Falha em {url}: Erro inesperado: {e.__class__.__name__} - {e}")
            return None 
    return None

def save_history_to_db(history_records):
    """
    Salva os registros de scrape (lista de dicts) na tabela 'scrape_history'.
    """
    if not history_records:
        print("No scrape history records to save.")
        return
    if not engine:
        print("Database engine not initialized. Exiting.")
        return

    print(f"\nSaving {len(history_records)} history records to database...")
    history_table = table("scrape_history",
        column("page_id"), column("scrape_timestamp"), column("modified_date"),
        column("updated_by"), column("responsible"), column("full_modified_text")
    )
    try:
        with engine.begin() as conn:
            conn.execute(insert(history_table), history_records)
        print(f"Successfully saved {len(history_records)} records to database.")
    except Exception as e:
        print(f"Error saving history to database: {e}")

if __name__ == "__main__":
    pages_to_scrape = load_pages_from_db()
    if not pages_to_scrape:
        print("No pages to scrape. Exiting script.")
    else:
        results = []
        driver = setup_driver()
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
        save_history_to_db(results)