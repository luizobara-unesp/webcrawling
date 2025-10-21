import time
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
        print(f"Error: Could not find all elements on page {url}. Details: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing {url}: {e}")
        return None

if __name__ == "__main__":
    
    pages_to_scrape = [
        {"id": "administracao", "url": "https://www.sorocaba.unesp.br/#!/sobre-o-campus/administracao/"},
    ]
    
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
                print(f"Found Data: {info}")
                
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

    print("\n--- FINAL RESULTS ---")
    import json
    print(json.dumps(results, indent=2, ensure_ascii=False))