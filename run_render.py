#!/usr/bin/env python3
"""
Файл запуска для Render.com
"""
import logging
import os
from main import run_bot


if __name__ == "__main__":
    # Увеличиваем уровень логирования для ясности в логах Render
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    
    # Запускаем бота
    run_bot()