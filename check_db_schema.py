import psycopg2
from config import Config

def check_events_table():
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        
        cur = conn.cursor()
        
        # Проверяем структуру таблицы events
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'events'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        print("Структура таблицы events:")
        for col in columns:
            print(f"  {col[0]} | {col[1]} | nullable: {col[2]} | default: {col[3]}")
        
        # Проверяем ограничения
        cur.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints 
            WHERE table_name = 'events';
        """)
        
        constraints = cur.fetchall()
        print("\nОграничения таблицы events:")
        for constraint in constraints:
            print(f"  {constraint[0]} | {constraint[1]}")
            
        # Проверяем детали check constraint
        cur.execute("""
            SELECT cc.constraint_name, cc.check_clause
            FROM information_schema.check_constraints cc
            JOIN information_schema.table_constraints tc 
            ON cc.constraint_name = tc.constraint_name
            WHERE tc.table_name = 'events';
        """)
        
        check_constraints = cur.fetchall()
        print("\nCheck constraints:")
        for check in check_constraints:
            print(f"  {check[0]}: {check[1]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")

def check_goals_table():
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        
        cur = conn.cursor()
        
        # Проверяем структуру таблицы goals
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'goals'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        print("Структура таблицы goals:")
        for col in columns:
            print(f"  {col[0]} | {col[1]} | nullable: {col[2]} | default: {col[3]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")

def check_users_table():
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        
        cur = conn.cursor()
        
        # Проверяем структуру таблицы users
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """)
        
        columns = cur.fetchall()
        print("Структура таблицы users:")
        for col in columns:
            print(f"  {col[0]} | {col[1]} | nullable: {col[2]} | default: {col[3]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_events_table()
    check_goals_table()
    check_users_table()