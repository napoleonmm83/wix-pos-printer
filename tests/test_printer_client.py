"""
Unit tests for the printer client.
Tests printer connection, status checking, and printing operations.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from wix_printer_service.printer_client import (
    PrinterClient, PrinterConnectionType, PrinterStatus, PrinterError
)


class TestPrinterClient:
    """Test cases for the PrinterClient class."""
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    def test_init_dummy_connection(self):
        """Test initialization with dummy connection."""
        client = PrinterClient()
        
        assert client.connection_type == PrinterConnectionType.DUMMY
        assert not client.is_connected
    
    @patch.dict(os.environ, {
        'PRINTER_CONNECTION_TYPE': 'usb',
        'PRINTER_USB_VENDOR_ID': '0x04b8',
        'PRINTER_USB_PRODUCT_ID': '0x0202'
    })
    def test_init_usb_connection(self):
        """Test initialization with USB connection."""
        client = PrinterClient()
        
        assert client.connection_type == PrinterConnectionType.USB
        assert client.usb_vendor_id == 0x04b8
        assert client.usb_product_id == 0x0202
    
    @patch.dict(os.environ, {
        'PRINTER_CONNECTION_TYPE': 'network',
        'PRINTER_NETWORK_HOST': '192.168.1.100',
        'PRINTER_NETWORK_PORT': '9100'
    })
    def test_init_network_connection(self):
        """Test initialization with network connection."""
        client = PrinterClient()
        
        assert client.connection_type == PrinterConnectionType.NETWORK
        assert client.network_host == '192.168.1.100'
        assert client.network_port == 9100
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_connect_dummy_success(self, mock_dummy):
        """Test successful connection with dummy printer."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        result = client.connect()
        
        assert result is True
        assert client.is_connected is True
        assert client.printer == mock_printer
        mock_dummy.assert_called_once()
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_connect_dummy_failure(self, mock_dummy):
        """Test connection failure with dummy printer."""
        mock_dummy.side_effect = Exception("Connection failed")
        
        client = PrinterClient()
        result = client.connect()
        
        assert result is False
        assert client.is_connected is False
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    def test_get_status_not_connected(self):
        """Test status check when not connected."""
        client = PrinterClient()
        status = client.get_status()
        
        assert status == PrinterStatus.OFFLINE
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_get_status_dummy_online(self, mock_dummy):
        """Test status check with dummy printer (always online)."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        status = client.get_status()
        
        assert status == PrinterStatus.ONLINE
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_print_text_success(self, mock_dummy):
        """Test successful text printing."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        result = client.print_text("Test content")
        
        assert result is True
        mock_printer.text.assert_called_once_with("Test content")
        mock_printer.ln.assert_called_with(2)
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    def test_print_text_not_connected(self):
        """Test text printing when not connected."""
        client = PrinterClient()
        result = client.print_text("Test content")
        
        assert result is False
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_print_text_printer_error(self, mock_dummy):
        """Test text printing with printer error."""
        mock_printer = Mock()
        mock_printer.text.side_effect = Exception("Printer error")
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        result = client.print_text("Test content")
        
        assert result is False
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_print_receipt_success(self, mock_dummy):
        """Test successful receipt printing."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        result = client.print_receipt("Receipt content", "Test Receipt")
        
        assert result is True
        mock_printer.init.assert_called_once()
        mock_printer.set.assert_called()
        mock_printer.text.assert_called()
        mock_printer.ln.assert_called_with(2)
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_print_receipt_without_title(self, mock_dummy):
        """Test receipt printing without title."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        result = client.print_receipt("Receipt content")
        
        assert result is True
        mock_printer.init.assert_called_once()
        mock_printer.text.assert_called()
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    @patch('wix_printer_service.printer_client.Dummy')
    def test_disconnect(self, mock_dummy):
        """Test printer disconnection."""
        mock_printer = Mock()
        mock_dummy.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        client.disconnect()
        
        assert client.is_connected is False
        mock_printer.close.assert_called_once()
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'dummy'})
    def test_get_printer_info(self):
        """Test getting printer information."""
        client = PrinterClient()
        info = client.get_printer_info()
        
        assert info['connection_type'] == 'dummy'
        assert info['is_connected'] is False
        assert info['status'] == 'offline'
        assert 'usb_vendor_id' in info
        assert 'network_host' in info
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'invalid'})
    def test_connect_invalid_connection_type(self):
        """Test connection with invalid connection type."""
        with pytest.raises(ValueError):
            PrinterClient()
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'usb'})
    @patch('wix_printer_service.printer_client.Usb')
    def test_connect_usb_with_parameters(self, mock_usb):
        """Test USB connection with specific parameters."""
        mock_printer = Mock()
        mock_usb.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        mock_usb.assert_called_once_with(
            idVendor=0x04b8,
            idProduct=0x0202,
            timeout=5000
        )
    
    @patch.dict(os.environ, {'PRINTER_CONNECTION_TYPE': 'network'})
    @patch('wix_printer_service.printer_client.Network')
    def test_connect_network_with_parameters(self, mock_network):
        """Test network connection with specific parameters."""
        mock_printer = Mock()
        mock_network.return_value = mock_printer
        
        client = PrinterClient()
        client.connect()
        
        mock_network.assert_called_once_with(
            host='192.168.1.100',
            port=9100,
            timeout=5
        )
