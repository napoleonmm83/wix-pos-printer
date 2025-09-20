"""
Main entry point for the Wix Printer Service.
This module starts the FastAPI application using uvicorn.
"""
import logging
import sys
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("wix_printer_service.log")
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Start the Wix Printer Service."""
    logger.info("Starting Wix Printer Service...")
    
    try:
        uvicorn.run(
            "wix_printer_service.api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload in production
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
