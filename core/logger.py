import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str = "entellibot", level: int = logging.INFO) -> logging.Logger:
    """Logger sozlamasi"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Agar handlerlar allaqachon qo'shilgan bo'lsa, qaytaramiz
    if logger.handlers:
        return logger

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (rotating) — logs papkasi yo'q bo'lsa avtomatik yaratamiz
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "bot.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Docker/Containerda faqat konsolga chiqarish kifoya
        print(f"File logger initialization skipped: {e}", file=sys.stderr)

    return logger


logger = setup_logger()
