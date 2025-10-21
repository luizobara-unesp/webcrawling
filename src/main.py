import time
import csv  # Importa a biblioteca CSV
import json # Usado apenas para imprimir o 'Found Data'
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

DRIVER_PATH = r'C:\Users\USER\projects\webcrawling\drivers\chromedriver.exe'

def setup_driver():
    """Inicializa e retorna uma instância do Selenium WebDriver."""
    print("Setting up Chrome driver (headless mode)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    
    service = Service(executable_path=DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Driver setup complete.")
    return driver

def load_pages_from_csv(filename="pages_to_scrape.csv"):
    """
    Carrega a lista de páginas a partir de um arquivo CSV.
    Retorna uma lista de dicionários (ex: [{'id': '...', 'url': '...'}]).
    """
    pages = []
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pages.append(row)
        print(f"Successfully loaded {len(pages)} pages from {filename}.")
        return pages
    except FileNotFoundError:
        print(f"--- ERRO ---")
        print(f"Arquivo '{filename}' não encontrado.")
        print(f"Por favor, rode o 'python src/crawl.py' primeiro para gerar o arquivo.")
        return []

def get_last_modified_info(driver, url):
    """
    Navega para uma URL específica e extrai as informações detalhadas de 
    modificação.
    
    Retorna um dicionário com os dados ou None se não for encontrado.
    """
    print(f"Navigating to: {url}")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        container_id = "idCorpoRodape"
        
        print(f"Waiting for element with ID: {container_id}...")
        container_element = wait.until(EC.presence_of_element_located((By.ID, container_id)))
        
        print("Container found. Extracting specific data...")
        
        full_text = container_element.text
        date_time_str = container_element.find_element(By.ID, "data-atualizacao-pagina").text
        date_str = date_time_str.split(' ')[0] 
        updated_by_str = container_element.find_element(By.ID, "usuario-atualizacao-pagina").text
        responsible_str = container_element.find_element(By.ID, "responsavel-pagina").text
        
        return {
            "last_modified": full_text,
            "date": date_str,
            "updated_by": updated_by_str,
            "responsible": responsible_str
        }

    except (TimeoutException, NoSuchElementException) as e:
        print(f"Error: Could not find all elements on page {url}. Details: {e.__class__.__name__}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing {url}: {e}")
        return None

def save_results_to_csv(results, filename="results.csv"):
    """Salva os resultados finais da extração em um arquivo CSV."""
    if not results:
        print("No results to save.")
        return

    print(f"\nSaving {len(results)} results to {filename}...")
    
    fieldnames = results[0].keys()
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
    print(f"Successfully saved results to {filename}")

if __name__ == "__main__":
    
    pages_to_scrape = load_pages_from_csv("pages_to_scrape.csv")
    
    if not pages_to_scrape:
        print("Exiting script.")
    else:
        results = []
        driver = setup_driver() 

        try:
            for page in pages_to_scrape:
                page_id = page["id"]
                page_url = page["url"]
                
                print(f"\n--- Scraping Page: {page_id} ---")
                
                info = get_last_modified_info(driver, page_url)
                
                result_data = {"id": page_id, "url": page_url}
                
                if info:
                    print(f"--- SUCCESS ({page_id}) ---")
                    # Imprime o que encontrou
                    print(f"Found Data: {json.dumps(info, indent=2, ensure_ascii=False)}")
                    result_data.update(info) 
                else:
                    print(f"--- FAILED ({page_id}) ---")
                    result_data.update({
                        "last_modified": "Not Found",
                        "date": "Not Found",
                        "updated_by": "Not Found",
                        "responsible": "Not Found"
                    })
                
                results.append(result_data)
                time.sleep(1) 

        finally:
            print("\nScraping complete. Closing driver.")
            driver.quit()

        # 2. Salva os resultados no CSV
        save_results_to_csv(results)