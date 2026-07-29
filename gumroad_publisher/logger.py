"""logger.py - Structured logging for every pipeline run."""
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

RESET="\033[0m";BOLD="\033[1m";GREEN="\033[92m";YELLOW="\033[93m"
RED="\033[91m";CYAN="\033[96m";DIM="\033[2m"
LEVEL_COLORS={"DEBUG":DIM,"INFO":CYAN,"SUCCESS":GREEN+BOLD,"WARNING":YELLOW,"ERROR":RED,"CRITICAL":RED+BOLD}
SUCCESS_LEVEL=25
logging.addLevelName(SUCCESS_LEVEL,"SUCCESS")

class ColorFormatter(logging.Formatter):
    def format(self,record):
        level=record.levelname;color=LEVEL_COLORS.get(level,"")
        ts=datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        prefix=f"{DIM}[{ts}]{RESET} {color}{level:<8}{RESET}"
        return f"{prefix} {record.getMessage()}"

class PlainFormatter(logging.Formatter):
    def format(self,record):
        ts=datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        return f"[{ts}] [{record.levelname:<8}] {record.getMessage()}"

def build_logger(log_file:str, session_id:str=None)->logging.Logger:
    session_id=session_id or uuid.uuid4().hex[:8].upper()
    logger=logging.getLogger(f"gumroad.{session_id}")
    logger.setLevel(logging.DEBUG)
    if logger.handlers: logger.handlers.clear()
    sh=logging.StreamHandler(sys.stdout);sh.setLevel(logging.DEBUG);sh.setFormatter(ColorFormatter())
    logger.addHandler(sh)
    log_path=Path(log_file);log_path.parent.mkdir(parents=True,exist_ok=True)
    fh=logging.FileHandler(log_path,encoding="utf-8");fh.setLevel(logging.DEBUG);fh.setFormatter(PlainFormatter())
    logger.addHandler(fh)
    logger.success=lambda msg,*a,**k:logger.log(SUCCESS_LEVEL,msg,*a,**k)
    logger.session_id=session_id
    logger.info(f"{'='*55}")
    logger.info(f"  Gumroad Auto-Publisher  |  Session {session_id}")
    logger.info(f"  Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*55}")
    return logger
