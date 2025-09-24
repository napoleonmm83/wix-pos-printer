#!/bin/bash

# Restaurant Configuration Setup Wizard
# Creates customized configuration for any restaurant type

set -e

echo "🍽️  RESTAURANT RECEIPT CONFIGURATION WIZARD"
echo "=============================================="
echo ""
echo "This wizard will help you configure receipt formatting for your restaurant."
echo ""

# Function to prompt for input with default value
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local result

    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " result
        result=${result:-$default}
    else
        read -p "$prompt: " result
    fi

    echo "$result"
}

# Function to select from options
select_option() {
    local prompt="$1"
    shift
    local options=("$@")

    echo "$prompt"
    for i in "${!options[@]}"; do
        echo "$((i+1)). ${options[i]}"
    done

    while true; do
        read -p "Enter choice (1-${#options[@]}): " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#options[@]}" ]; then
            echo "${options[$((choice-1))]}"
            return
        else
            echo "Invalid choice. Please enter a number between 1 and ${#options[@]}."
        fi
    done
}

# Create config directory
CONFIG_DIR="config"
mkdir -p "$CONFIG_DIR"

echo "📋 BASIC RESTAURANT INFORMATION"
echo "-------------------------------"

RESTAURANT_NAME=$(prompt_with_default "Restaurant Name" "My Restaurant")
RESTAURANT_ADDRESS1=$(prompt_with_default "Address Line 1" "123 Main Street")
RESTAURANT_ADDRESS2=$(prompt_with_default "Address Line 2 (City, Postal Code)" "12345 Your City")
RESTAURANT_ADDRESS3=$(prompt_with_default "Address Line 3 (Country)" "Your Country")
RESTAURANT_PHONE=$(prompt_with_default "Phone Number" "+1 234 567 8900")
RESTAURANT_EMAIL=$(prompt_with_default "Email Address" "info@restaurant.com")

echo ""
echo "🍳 CUISINE TYPE SELECTION"
echo "-------------------------"

CUISINE_OPTIONS=(
    "thai - Thai Restaurant (🍜 with Thai branding)"
    "italian - Italian Restaurant (🍝 with Italian style)"
    "mexican - Mexican Restaurant (🌮 with Mexican flair)"
    "german - German Restaurant (🥨 with German style)"
    "generic - Generic Restaurant (🍽️ universal style)"
)

CUISINE_SELECTION=$(select_option "Select your cuisine type:" "${CUISINE_OPTIONS[@]}")
CUISINE_TYPE=$(echo "$CUISINE_SELECTION" | cut -d' ' -f1)

echo ""
echo "💰 REGIONAL SETTINGS"
echo "--------------------"

REGION_OPTIONS=(
    "switzerland - Switzerland (CHF, 0% food tax)"
    "germany - Germany (EUR, 7% food tax)"
    "austria - Austria (EUR, 10% food tax)"
    "usa - United States (USD, varies by state)"
    "uk - United Kingdom (GBP, 0% food tax)"
    "custom - Custom settings"
)

REGION_SELECTION=$(select_option "Select your region:" "${REGION_OPTIONS[@]}")
REGION_TYPE=$(echo "$REGION_SELECTION" | cut -d' ' -f1)

# Handle custom currency if needed
if [ "$REGION_TYPE" = "custom" ]; then
    echo ""
    echo "💱 CUSTOM CURRENCY SETTINGS"
    echo "---------------------------"

    CURRENCY_CODE=$(prompt_with_default "Currency Code (e.g., EUR, USD, CHF)" "EUR")
    CURRENCY_SYMBOL=$(prompt_with_default "Currency Symbol" "€")
    TAX_RATE=$(prompt_with_default "Default Tax Rate (as decimal, e.g., 0.19 for 19%)" "0.19")
    BUSINESS_ID=$(prompt_with_default "Business ID Format" "Business ID: XXX-XXX-XXX")
else
    # Use regional defaults
    case "$REGION_TYPE" in
        "switzerland")
            CURRENCY_CODE="CHF"
            CURRENCY_SYMBOL="CHF"
            TAX_RATE="0.0"
            BUSINESS_ID="CHE-XXX.XXX.XXX MWST"
            ;;
        "germany")
            CURRENCY_CODE="EUR"
            CURRENCY_SYMBOL="€"
            TAX_RATE="0.07"
            BUSINESS_ID="DE123456789"
            ;;
        "austria")
            CURRENCY_CODE="EUR"
            CURRENCY_SYMBOL="€"
            TAX_RATE="0.10"
            BUSINESS_ID="ATU12345678"
            ;;
        "usa")
            CURRENCY_CODE="USD"
            CURRENCY_SYMBOL="$"
            TAX_RATE="0.0875"
            BUSINESS_ID="EIN: XX-XXXXXXX"
            ;;
        "uk")
            CURRENCY_CODE="GBP"
            CURRENCY_SYMBOL="£"
            TAX_RATE="0.0"
            BUSINESS_ID="GB123456789"
            ;;
    esac
fi

echo ""
echo "🌍 LANGUAGE SETTINGS"
echo "-------------------"

LANGUAGE_OPTIONS=(
    "de - German"
    "en - English"
    "fr - French"
    "it - Italian"
)

LANGUAGE_SELECTION=$(select_option "Select receipt language:" "${LANGUAGE_OPTIONS[@]}")
LANGUAGE=$(echo "$LANGUAGE_SELECTION" | cut -d' ' -f1)

echo ""
echo "📄 CONFIGURATION SUMMARY"
echo "========================"
echo "Restaurant: $RESTAURANT_NAME"
echo "Cuisine: $CUISINE_TYPE"
echo "Region: $REGION_TYPE"
echo "Currency: $CURRENCY_CODE ($CURRENCY_SYMBOL)"
echo "Language: $LANGUAGE"
echo ""

read -p "Create configuration with these settings? (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Configuration cancelled."
    exit 0
fi

# Generate restaurant_config.yaml
cat > "$CONFIG_DIR/restaurant_config.yaml" << EOF
# Restaurant Configuration
# Generated by setup wizard on $(date)

restaurant:
  name: "$RESTAURANT_NAME"
  address:
    - "$RESTAURANT_ADDRESS1"
    - "$RESTAURANT_ADDRESS2"
    - "$RESTAURANT_ADDRESS3"
  phone: "$RESTAURANT_PHONE"
  email: "$RESTAURANT_EMAIL"

branding:
  cuisine_type: "$CUISINE_TYPE"

currency:
  code: "$CURRENCY_CODE"
  symbol: "$CURRENCY_SYMBOL"

tax:
  default_rate: $TAX_RATE
  business_id: "$BUSINESS_ID"

localization:
  language: "$LANGUAGE"
EOF

# Set environment variable for region
echo ""
echo "📝 ENVIRONMENT SETUP"
echo "-------------------"

ENV_FILE=".env.local"

# Create or update .env.local with region setting
if [ -f "$ENV_FILE" ]; then
    # Remove existing RESTAURANT_REGION if present
    grep -v "^RESTAURANT_REGION=" "$ENV_FILE" > "${ENV_FILE}.tmp" || true
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
fi

echo "RESTAURANT_REGION=$REGION_TYPE" >> "$ENV_FILE"

echo "✅ CONFIGURATION COMPLETE!"
echo "=========================="
echo ""
echo "Configuration files created:"
echo "📁 $CONFIG_DIR/restaurant_config.yaml - Main restaurant settings"
echo "📁 $ENV_FILE - Environment variables (RESTAURANT_REGION=$REGION_TYPE)"
echo ""
echo "Your receipt formatter is now configured for:"
echo "🍽️  $RESTAURANT_NAME ($CUISINE_TYPE cuisine)"
echo "💰 $CURRENCY_CODE currency with $TAX_RATE tax rate"
echo "🌍 $LANGUAGE language in $REGION_TYPE region"
echo ""
echo "Test your configuration:"
echo "   python test_thai_receipts.py"
echo ""
echo "To reconfigure, run this script again:"
echo "   ./scripts/setup-restaurant-config.sh"
echo ""

# Offer to create sample receipt
read -p "Would you like to create a sample receipt now? (y/n): " create_sample

if [ "$create_sample" = "y" ] || [ "$create_sample" = "Y" ]; then
    echo ""
    echo "🧾 Creating sample receipt..."

    # Check if Python environment is available
    if command -v python3 &> /dev/null; then
        python3 -c "
from wix_printer_service.config_manager import reload_config
from wix_printer_service.configurable_receipt_formatter import ConfigurableKitchenReceiptFormatter

# Reload config with new settings
config = reload_config()

print('\\n' + '='*50)
print('SAMPLE KITCHEN RECEIPT')
print('='*50)
print(f'Restaurant: {config.restaurant.name}')
print(f'Cuisine: {config.branding.cuisine_type}')
print(f'Currency: {config.localization.currency.code}')
print('='*50)

# Note: Full sample would require actual order data
print('Configuration loaded successfully!')
print('Run test_thai_receipts.py with real order data to see full receipts.')
" 2>/dev/null || echo "Python environment not ready. Run 'python test_thai_receipts.py' manually when ready."
    else
        echo "Python not found. Run 'python test_thai_receipts.py' when your environment is ready."
    fi
fi

echo ""
echo "🎉 Setup complete! Your restaurant receipt system is ready to use."