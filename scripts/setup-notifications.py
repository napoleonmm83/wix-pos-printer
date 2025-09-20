#!/usr/bin/env python3
"""
Notification Service Setup Script
Konfiguriert E-Mail-Benachrichtigungen für Story 2.3
"""

import os
import sys
import json
import getpass
import smtplib
from pathlib import Path
from email.mime.text import MIMEText

def test_smtp_connection(smtp_server, smtp_port, username, password, use_tls=True):
    """Test SMTP connection with provided credentials."""
    try:
        print(f"Testing SMTP connection to {smtp_server}:{smtp_port}...")
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
                print("✓ TLS connection established")
            
            if username and password:
                server.login(username, password)
                print("✓ Authentication successful")
            
            print("✓ SMTP connection test successful!")
            return True
            
    except Exception as e:
        print(f"✗ SMTP connection failed: {e}")
        return False

def send_test_email(smtp_server, smtp_port, username, password, from_email, to_email, use_tls=True):
    """Send a test email to verify configuration."""
    try:
        print(f"Sending test email to {to_email}...")
        
        # Create test message
        msg = MIMEText("""
Dies ist eine Test-E-Mail vom Wix Printer Service.

Wenn Sie diese E-Mail erhalten, ist die Benachrichtigungskonfiguration erfolgreich eingerichtet.

Zeitstempel: {timestamp}
Restaurant: Test Restaurant
System: Wix Printer Service

Diese E-Mail wurde automatisch generiert. Bitte nicht antworten.
        """.strip().format(timestamp=__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        msg['Subject'] = '🧪 Test-Benachrichtigung - Wix Printer Service'
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            
            if username and password:
                server.login(username, password)
            
            server.send_message(msg)
        
        print("✓ Test email sent successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Failed to send test email: {e}")
        return False

def get_smtp_providers():
    """Get common SMTP provider configurations."""
    return {
        "gmail": {
            "name": "Gmail",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "use_tls": True,
            "instructions": "Use App Password, not regular password. Enable 2FA first."
        },
        "outlook": {
            "name": "Outlook/Hotmail",
            "smtp_server": "smtp-mail.outlook.com",
            "smtp_port": 587,
            "use_tls": True,
            "instructions": "Use regular password or App Password if 2FA enabled."
        },
        "yahoo": {
            "name": "Yahoo Mail",
            "smtp_server": "smtp.mail.yahoo.com",
            "smtp_port": 587,
            "use_tls": True,
            "instructions": "Use App Password, not regular password."
        },
        "custom": {
            "name": "Custom SMTP Server",
            "smtp_server": "",
            "smtp_port": 587,
            "use_tls": True,
            "instructions": "Enter your custom SMTP server details."
        }
    }

def interactive_setup():
    """Interactive notification setup."""
    print("🔧 Wix Printer Service - Notification Setup")
    print("=" * 50)
    
    # Show SMTP providers
    providers = get_smtp_providers()
    print("\nVerfügbare E-Mail-Anbieter:")
    for key, provider in providers.items():
        print(f"  {key}: {provider['name']}")
    
    # Select provider
    while True:
        provider_choice = input("\nWählen Sie einen Anbieter (gmail/outlook/yahoo/custom): ").lower().strip()
        if provider_choice in providers:
            break
        print("Ungültige Auswahl. Bitte wählen Sie gmail, outlook, yahoo oder custom.")
    
    provider = providers[provider_choice]
    print(f"\n📧 Konfiguration für {provider['name']}")
    print(f"Hinweis: {provider['instructions']}")
    
    # Get SMTP settings
    if provider_choice == "custom":
        smtp_server = input("SMTP Server: ").strip()
        smtp_port = int(input("SMTP Port (587): ").strip() or "587")
        use_tls = input("TLS verwenden? (y/n) [y]: ").strip().lower() != 'n'
    else:
        smtp_server = provider["smtp_server"]
        smtp_port = provider["smtp_port"]
        use_tls = provider["use_tls"]
        print(f"SMTP Server: {smtp_server}:{smtp_port} (TLS: {use_tls})")
    
    # Get credentials
    username = input("E-Mail-Adresse: ").strip()
    password = getpass.getpass("Passwort (App Password empfohlen): ")
    
    # Get notification settings
    from_email = input(f"Absender-E-Mail [{username}]: ").strip() or username
    
    print("\nEmpfänger-E-Mails (kommagetrennt):")
    to_emails = input("E-Mail-Adressen: ").strip()
    to_emails_list = [email.strip() for email in to_emails.split(",") if email.strip()]
    
    restaurant_name = input("Restaurant Name [Mein Restaurant]: ").strip() or "Mein Restaurant"
    
    # Test connection
    print("\n🔍 Teste SMTP-Verbindung...")
    if not test_smtp_connection(smtp_server, smtp_port, username, password, use_tls):
        print("❌ SMTP-Test fehlgeschlagen. Bitte überprüfen Sie Ihre Einstellungen.")
        return None
    
    # Send test email
    if to_emails_list:
        test_email = to_emails_list[0]
        send_test = input(f"\nTest-E-Mail an {test_email} senden? (y/n) [y]: ").strip().lower() != 'n'
        
        if send_test:
            if not send_test_email(smtp_server, smtp_port, username, password, from_email, test_email, use_tls):
                print("⚠️  Test-E-Mail fehlgeschlagen, aber SMTP-Verbindung funktioniert.")
    
    # Return configuration
    return {
        "smtp_server": smtp_server,
        "smtp_port": smtp_port,
        "smtp_username": username,
        "smtp_password": password,
        "smtp_use_tls": use_tls,
        "from_email": from_email,
        "to_emails": to_emails_list,
        "restaurant_name": restaurant_name,
        "enabled": True
    }

def update_env_file(config, env_file_path=".env"):
    """Update .env file with notification configuration."""
    try:
        env_path = Path(env_file_path)
        
        # Read existing .env file
        env_lines = []
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Configuration mapping
        env_vars = {
            "NOTIFICATION_ENABLED": str(config["enabled"]).lower(),
            "SMTP_SERVER": config["smtp_server"],
            "SMTP_PORT": str(config["smtp_port"]),
            "SMTP_USE_TLS": str(config["smtp_use_tls"]).lower(),
            "SMTP_USERNAME": config["smtp_username"],
            "SMTP_PASSWORD": config["smtp_password"],
            "NOTIFICATION_FROM_EMAIL": config["from_email"],
            "NOTIFICATION_TO_EMAILS": ",".join(config["to_emails"]),
            "RESTAURANT_NAME": config["restaurant_name"]
        }
        
        # Update or add environment variables
        updated_vars = set()
        for i, line in enumerate(env_lines):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key = line.split('=')[0]
                if key in env_vars:
                    env_lines[i] = f"{key}={env_vars[key]}\n"
                    updated_vars.add(key)
        
        # Add new variables
        for key, value in env_vars.items():
            if key not in updated_vars:
                env_lines.append(f"{key}={value}\n")
        
        # Write updated .env file
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        print(f"✓ .env file updated: {env_path}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to update .env file: {e}")
        return False

def save_config_json(config, config_file_path="config/notifications.json"):
    """Save configuration to JSON file."""
    try:
        config_path = Path(config_file_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove password from JSON config for security
        json_config = config.copy()
        json_config["smtp_password"] = "***CONFIGURED***"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(json_config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Configuration saved: {config_path}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to save configuration: {e}")
        return False

def run_database_migration():
    """Run database migrations for notification tables."""
    try:
        print("\n🗄️  Running database migrations...")
        
        # Import and run migrations
        sys.path.append(str(Path(__file__).parent.parent))
        from wix_printer_service.database_migrations import run_migrations
        
        database_path = "data/printer_service.db"
        success = run_migrations(database_path)
        
        if success:
            print("✓ Database migrations completed successfully")
        else:
            print("✗ Database migrations failed")
        
        return success
        
    except Exception as e:
        print(f"✗ Error running database migrations: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 Wix Printer Service - Notification Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("wix_printer_service").exists():
        print("❌ Bitte führen Sie dieses Script aus dem Projekt-Root-Verzeichnis aus.")
        sys.exit(1)
    
    # Interactive setup
    config = interactive_setup()
    if not config:
        print("❌ Setup abgebrochen.")
        sys.exit(1)
    
    print("\n💾 Speichere Konfiguration...")
    
    # Update .env file
    env_success = update_env_file(config)
    
    # Save JSON config
    json_success = save_config_json(config)
    
    # Run database migrations
    migration_success = run_database_migration()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Setup-Zusammenfassung:")
    print(f"  ✓ SMTP-Verbindung: Erfolgreich getestet")
    print(f"  {'✓' if env_success else '✗'} .env Datei: {'Aktualisiert' if env_success else 'Fehler'}")
    print(f"  {'✓' if json_success else '✗'} JSON Config: {'Gespeichert' if json_success else 'Fehler'}")
    print(f"  {'✓' if migration_success else '✗'} Datenbank: {'Migriert' if migration_success else 'Fehler'}")
    
    if env_success and json_success and migration_success:
        print("\n🎉 Notification Setup erfolgreich abgeschlossen!")
        print("\nNächste Schritte:")
        print("1. Starten Sie den Wix Printer Service neu")
        print("2. Testen Sie die Benachrichtigungen über die API:")
        print("   curl -X POST http://localhost:8000/notifications/test")
        print("3. Überwachen Sie die Logs für Benachrichtigungs-Events")
    else:
        print("\n⚠️  Setup teilweise fehlgeschlagen. Bitte überprüfen Sie die Fehler oben.")
    
    print("\n📚 Weitere Informationen:")
    print("  - API Dokumentation: http://localhost:8000/docs")
    print("  - Notification Status: http://localhost:8000/notifications/status")
    print("  - Configuration: config/notifications.json")

if __name__ == "__main__":
    main()
