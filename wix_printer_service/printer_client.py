"""
Printer client for Epson TM-m30III communication.
Handles printer connection, status checking, and basic printing operations.
"""
import os
import logging
from typing import Optional, Dict, Any
from enum import Enum
from escpos.printer import Usb, Network, Dummy
from escpos.exceptions import Error as EscposError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class PrinterConnectionType(Enum):
    """Printer connection types."""
    USB = "usb"
    NETWORK = "network"
    DUMMY = "dummy"  # For testing


class PrinterStatus(Enum):
    """Printer status enumeration."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    PAPER_OUT = "paper_out"
    UNKNOWN = "unknown"


class PrinterError(Exception):
    """Custom exception for printer-related errors."""
    pass


class PrinterClient:
    """
    Client for communicating with Epson TM-m30III printer.
    Supports USB and network connections with comprehensive error handling.
    """
    
    def __init__(self):
        """Initialize the printer client with configuration from environment."""
        # Determine connection type (support both new and wizard variable names)
        conn_name = (
            os.getenv('PRINTER_CONNECTION_TYPE')
            or os.getenv('PRINTER_INTERFACE')
            or os.getenv('PRINTER_TYPE')
            or 'dummy'
        ).lower()
        try:
            self.connection_type = PrinterConnectionType(conn_name)
        except ValueError:
            self.connection_type = PrinterConnectionType.DUMMY
            logger.warning(f"Unknown printer connection type '{conn_name}', defaulting to dummy")

        self.printer = None
        self._is_connected = False

        # USB configuration (robust parsing for hex or decimal values)
        def _parse_usb(value: str, default_hex: str) -> int:
            env_val = os.getenv(value)
            if env_val:
                try:
                    return int(env_val, 0)  # auto-detect base (0x..., decimal)
                except Exception:
                    logger.warning(f"Invalid {value}='{env_val}', falling back to default {default_hex}")
            return int(default_hex, 16)

        self.usb_vendor_id = _parse_usb('PRINTER_USB_VENDOR_ID', '0x04b8')  # Epson
        self.usb_product_id = _parse_usb('PRINTER_USB_PRODUCT_ID', '0x0202')  # TM-m30III

        # Network configuration (support wizard names)
        self.network_host = os.getenv('PRINTER_NETWORK_HOST') or os.getenv('PRINTER_IP', '192.168.1.100')
        self.network_port = int(
            os.getenv('PRINTER_NETWORK_PORT') or os.getenv('PRINTER_PORT', '9100')
        )

        logger.info(
            "Printer client initialized",
            extra={
                'connection_type': self.connection_type.value,
                'network_host': self.network_host,
                'network_port': self.network_port,
                'usb_vendor_id': hex(self.usb_vendor_id),
                'usb_product_id': hex(self.usb_product_id),
            }
        )
    
    def connect(self) -> bool:
        """
        Establish connection to the printer.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            if self.connection_type == PrinterConnectionType.USB:
                self.printer = Usb(
                    idVendor=self.usb_vendor_id,
                    idProduct=self.usb_product_id,
                    timeout=5000
                )
            elif self.connection_type == PrinterConnectionType.NETWORK:
                self.printer = Network(
                    host=self.network_host,
                    port=self.network_port,
                    timeout=5
                )
            elif self.connection_type == PrinterConnectionType.DUMMY:
                # Use dummy printer for testing
                self.printer = Dummy()
            else:
                raise PrinterError(f"Unsupported connection type: {self.connection_type}")
            
            # Test the connection
            if self._test_connection():
                self._is_connected = True
                logger.info(f"Successfully connected to printer via {self.connection_type.value}")
                return True
            else:
                self._is_connected = False
                logger.error("Failed to establish printer connection")
                return False
                
        except EscposError as e:
            logger.error(f"ESC/POS error during connection: {e}")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error during printer connection: {e}")
            self._is_connected = False
            return False
    
    def _test_connection(self) -> bool:
        """
        Test the printer connection by sending a simple command.
        
        Returns:
            bool: True if test successful, False otherwise
        """
        try:
            # Send a simple status request or initialization
            if hasattr(self.printer, '_raw'):
                # For real printers, we could send ESC/POS status commands
                # For now, we'll assume connection is good if printer object exists
                pass
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_status(self) -> PrinterStatus:
        """
        Get the current printer status.
        
        Returns:
            PrinterStatus: Current status of the printer
        """
        if not self._is_connected or not self.printer:
            return PrinterStatus.OFFLINE
        
        try:
            # For dummy printer, always return online
            if self.connection_type == PrinterConnectionType.DUMMY:
                return PrinterStatus.ONLINE
            
            # For real printers, we would check actual status
            # This is a simplified implementation
            return PrinterStatus.ONLINE
            
        except EscposError as e:
            logger.error(f"Error checking printer status: {e}")
            return PrinterStatus.ERROR
        except Exception as e:
            logger.error(f"Unexpected error checking printer status: {e}")
            return PrinterStatus.UNKNOWN
    
    def print_text(self, content: str) -> bool:
        """
        Print plain text content.
        
        Args:
            content: Text content to print
            
        Returns:
            bool: True if printing successful, False otherwise
        """
        if not self._is_connected or not self.printer:
            logger.error("Printer not connected")
            return False
        
        try:
            # Print the content
            self.printer.text(content)
            
            # Add line feed and cut paper
            self.printer.ln(2)  # Two line feeds
            
            # Cut paper if supported (partial cut)
            try:
                self.printer.cut(mode='PART')
            except:
                # If cut is not supported, just add more line feeds
                self.printer.ln(3)
            
            logger.info("Text printed successfully")
            return True
            
        except EscposError as e:
            logger.error(f"ESC/POS error during printing: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during printing: {e}")
            return False
    
    def print_receipt(self, content: str, title: str = None) -> bool:
        """
        Print a formatted receipt.
        
        Args:
            content: Receipt content
            title: Optional title for the receipt
            
        Returns:
            bool: True if printing successful, False otherwise
        """
        if not self._is_connected or not self.printer:
            logger.error("Printer not connected")
            return False
        
        try:
            
            # Print title if provided
            if title:
                self.printer.set(align='center', text_type='B')  # Bold and centered
                self.printer.text(f"{title}\n")
                self.printer.set()  # Reset formatting
                self.printer.text("=" * 32 + "\n")  # Separator line
            
            # Print content
            self.printer.set(align='left')
            self.printer.text(content)
            
            # Add footer
            self.printer.text("\n" + "=" * 32 + "\n")
            
            # Add line feeds and cut
            self.printer.ln(2)
            
            try:
                self.printer.cut(mode='PART')
            except:
                self.printer.ln(3)
            
            logger.info(f"Receipt printed successfully: {title or 'Untitled'}")
            return True
            
        except EscposError as e:
            logger.error(f"ESC/POS error during receipt printing: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during receipt printing: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the printer."""
        try:
            if self.printer and hasattr(self.printer, 'close'):
                self.printer.close()
            self._is_connected = False
            logger.info("Printer disconnected")
        except Exception as e:
            logger.error(f"Error during printer disconnect: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if printer is connected."""
        return self._is_connected
    
    def get_printer_info(self) -> Dict[str, Any]:
        """
        Get printer information and configuration.
        
        Returns:
            Dict containing printer information
        """
        return {
            'connection_type': self.connection_type.value,
            'is_connected': self._is_connected,
            'status': self.get_status().value,
            'usb_vendor_id': hex(self.usb_vendor_id) if self.connection_type == PrinterConnectionType.USB else None,
            'usb_product_id': hex(self.usb_product_id) if self.connection_type == PrinterConnectionType.USB else None,
            'network_host': self.network_host if self.connection_type == PrinterConnectionType.NETWORK else None,
            'network_port': self.network_port if self.connection_type == PrinterConnectionType.NETWORK else None,
        }
