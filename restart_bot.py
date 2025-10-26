import subprocess
import time
import sys
import os

def kill_python_processes():
    """Останавливает все процессы Python с main.py"""
    try:
        # Получаем список процессов Python
        result = subprocess.run(['wmic', 'process', 'where', 'name="python.exe"', 'get', 'processid,commandline'], 
                              capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        pids_to_kill = []
        
        for line in lines[1:]:  # Пропускаем заголовок
            if 'main.py' in line and line.strip():
                # Извлекаем PID из конца строки
                parts = line.strip().split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        pids_to_kill.append(pid)
                    except ValueError:
                        continue
        
        # Останавливаем процессы
        for pid in pids_to_kill:
            try:
                subprocess.run(['taskkill', '/PID', str(pid), '/F'], 
                             capture_output=True, check=False)
                print(f"Остановлен процесс PID: {pid}")
            except Exception as e:
                print(f"Ошибка остановки процесса {pid}: {e}")
        
        print(f"Остановлено {len(pids_to_kill)} процессов")
        return len(pids_to_kill) > 0
        
    except Exception as e:
        print(f"Ошибка при остановке процессов: {e}")
        return False

def start_bot():
    """Запускает бота"""
    print("Запускаю бота...")
    try:
        # Запускаем main.py
        subprocess.run([sys.executable, 'main.py'], check=True)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка запуска бота: {e}")

if __name__ == "__main__":
    print("Перезапуск бота...")
    
    # Останавливаем существующие процессы
    if kill_python_processes():
        print("Ожидание 3 секунды...")
        time.sleep(3)
    
    # Запускаем бота
    start_bot()
