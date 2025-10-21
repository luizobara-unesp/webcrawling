import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv

def get_db_engine():
    """
    Carrega as variáveis de ambiente e cria uma engine SQLAlchemy.
    """
    load_dotenv()
    
    db_url_str = os.environ.get('DATABASE_URL')
    
    if not db_url_str:
        raise ValueError("Variável de ambiente DATABASE_URL não definida.")
        
    try:
        engine = create_engine(db_url_str)
        return engine
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

engine = get_db_engine()