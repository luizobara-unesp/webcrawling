import time
import csv  # Importa a biblioteca CSV
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException

DRIVER_PATH = r'C:\Users\USER\projects\webcrawling\drivers\chromedriver.exe'

def setup_driver():
    """Inicializa o WebDriver em modo headless (sem janela)."""
    print("Setting up Chrome driver (headless mode)...")
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    
    service = Service(executable_path=DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Driver setup complete.")
    return driver

def generate_id_from_url(url_path):
    """
    Gera um ID a partir do path da URL.
    Ex: 'sobre-o-campus/administracao/' -> 'administracao'
    """
    try:
        parts = url_path.strip("/").split("/")
        if parts:
            # Pega o último item que não seja vazio
            last_part = next((part for part in reversed(parts) if part), None)
            return last_part if last_part else "homepage"
        return "homepage"
    except Exception:
        return "unknown"

def crawl_site(start_url):
    """
    Varre o site a partir da URL inicial em busca de todas as sub-páginas
    que usam o padrão '#!/'.
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
            
            # --- CORREÇÃO AQUI ---
            # Espera pelo rodapé, que deve existir em todas as páginas
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

def save_pages_to_csv(pages, filename="pages_to_scrape.csv"):
    """Salva a lista de páginas encontradas em um arquivo CSV."""
    if not pages:
        print("No pages found to save.")
        return

    print(f"\nSaving {len(pages)} pages to {filename}...")
    
    # 'fieldnames' são os cabeçalhos das colunas
    fieldnames = ['id', 'url']
    
    # 'w' = write (sobrescrever), newline='' é padrão para CSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader() # Escreve a linha de cabeçalho (id, url)
        writer.writerows(pages) # Escreve todos os dados
        
    print(f"Successfully saved to {filename}")

# --- Bloco de Execução Principal ---
if __name__ == "__main__":
    
    root_url = "https://www.sorocaba.unesp.br/#!/"
    
    print("Starting site crawl...")
    all_pages = crawl_site(root_url)
    
    print("\n--- CRAWL COMPLETE ---")
    
    # Salva os resultados no CSV
    save_pages_to_csv(all_pages)