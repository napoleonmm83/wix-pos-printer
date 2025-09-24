# 🍽️ Restaurant Configuration Guide

This system supports **any type of restaurant** with customizable receipt formatting. Whether you run a Thai restaurant, Italian pizzeria, German bakery, or any other food business - the system adapts to your needs.

## 🚀 Quick Setup (Recommended)

Run the configuration wizard to set up your restaurant in minutes:

```bash
./scripts/setup-restaurant-config.sh
```

The wizard will ask you about:
- **Restaurant details** (name, address, contact)
- **Cuisine type** (Thai, Italian, Mexican, German, or Generic)
- **Regional settings** (currency, tax rates, legal requirements)
- **Language preferences**

## 🏗️ Manual Configuration

### 1. Create Configuration Files

Create your restaurant configuration in `config/restaurant_config.yaml`:

```yaml
restaurant:
  name: "Your Restaurant Name"
  address:
    - "123 Your Street"
    - "12345 Your City"
    - "Your Country"
  phone: "+1 234 567 8900"
  email: "info@your-restaurant.com"

branding:
  cuisine_type: "thai"  # Options: thai, italian, mexican, german, generic

currency:
  code: "USD"
  symbol: "$"

tax:
  default_rate: 0.0875  # 8.75% (as decimal)
  business_id: "Your Business ID"

localization:
  language: "en"  # en, de, fr, it
```

### 2. Set Regional Settings

Set your region as an environment variable:

```bash
export RESTAURANT_REGION=usa
# Options: switzerland, germany, austria, usa, uk
```

Or add to your `.env.local`:

```
RESTAURANT_REGION=usa
```

## 🍳 Cuisine Templates

### Available Cuisine Types

#### 🍜 Thai Restaurant
```yaml
branding:
  cuisine_type: "thai"
```
- **Emojis**: 🍜 🍛 🍲 🥢
- **Thank you**: "🙏 Kob Khun Ka! 🙏 (Vielen Dank auf Thai)"
- **Prep times**: Optimized for Thai dishes (Pad Thai +3min, Curry +4min)

#### 🍝 Italian Restaurant
```yaml
branding:
  cuisine_type: "italian"
```
- **Emojis**: 🍝 🍕 🧀
- **Thank you**: "🇮🇹 Grazie Mille! 🇮🇹 (Vielen Dank auf Italienisch)"
- **Prep times**: Pizza +8min, Pasta +5min, Risotto +12min

#### 🌮 Mexican Restaurant
```yaml
branding:
  cuisine_type: "mexican"
```
- **Emojis**: 🌮 🌯 🌶️
- **Thank you**: "🇲🇽 ¡Muchas Gracias! 🇲🇽 (Vielen Dank auf Spanisch)"
- **Prep times**: Tacos +2min, Burrito +4min

#### 🥨 German Restaurant
```yaml
branding:
  cuisine_type: "german"
```
- **Emojis**: 🥨 🍺 🥖 🥩
- **Thank you**: "🇩🇪 Vielen Dank! 🇩🇪 (Herzlichen Dank)"

#### 🍽️ Generic Restaurant
```yaml
branding:
  cuisine_type: "generic"
```
- **Emojis**: 🍽️ 🍴 🥗 🍰
- **Thank you**: "✨ Vielen Dank! ✨ (Thank you very much)"

## 💰 Regional Settings

### 🇨🇭 Switzerland
- **Currency**: CHF (Swiss Francs)
- **Tax**: 0% for basic food, 7.7% for beverages
- **Business ID**: CHE-XXX.XXX.XXX MWST
- **Format**: CHF 26.00

### 🇩🇪 Germany
- **Currency**: EUR (Euros)
- **Tax**: 7% reduced rate for food, 19% standard
- **Business ID**: DE123456789
- **Format**: 26.00€

### 🇦🇹 Austria
- **Currency**: EUR (Euros)
- **Tax**: 10% reduced rate for food, 20% standard
- **Business ID**: ATU12345678
- **Format**: € 26.00

### 🇺🇸 United States
- **Currency**: USD (US Dollars)
- **Tax**: Varies by state (example: 8.75% NYC)
- **Business ID**: EIN: XX-XXXXXXX
- **Format**: $26.00

### 🇬🇧 United Kingdom
- **Currency**: GBP (British Pounds)
- **Tax**: 0% for most food, 20% VAT standard
- **Business ID**: GB123456789
- **Format**: £26.00

## 🧾 Receipt Types (Thermodrucker-optimiert)

The system generates three types of receipts, all customized to your settings and optimized for thermal printers:

### 🍳 Kitchen Receipt (`ConfigurableKitchenReceiptFormatter`)
- **Purpose**: Kitchen staff preparation (optimized for busy kitchen environment)
- **Design Philosophy**: Minimal, clear, fast to read under pressure
- **Features**:
  - **Clean header**: Just "KÜCHE" (no restaurant name clutter)
  - **No emojis**: Pure text for reliable thermal printing
  - **Clear service type**: "ABHOLUNG" or "LIEFERUNG"
  - **Bold item quantities**: "3x Nam Tok" for quick scanning
  - **Special instructions**: `>>> SPEZIELL: Notes <<<`
  - **Allergy warnings**: `!!! ALLERGIE WARNUNG !!!`
  - **Prep instructions**: `*** FRISCH ZUBEREITEN ***`

**Example Kitchen Receipt:**
```
KÜCHE
================================
BESTELLUNG #10033
Order ID: abc123...
Zeit: 18:30

LIEFERUNG
--------------------------------
GERICHTE:
3x Nam Tok
>>> SPEZIELL: Scharf <<<
2x Som Tam

================================
*** FRISCH ZUBEREITEN ***
```

### 🚗 Pickup/Delivery Receipt (`ConfigurableDriverReceiptFormatter`)
- **Purpose**: Service staff and delivery drivers
- **Features**:
  - **Restaurant branding**: "RESTAURANT - ABHOLUNG/LIEFERUNG"
  - **Customer contact information**
  - **Full addresses** for pickup/delivery
  - **Payment status** and totals
  - **Action prompts**: `>>> BEREIT ZUR ABHOLUNG <<<`
  - **No emoji clutter**: Clean thermal printer output

### 🧾 Customer Receipt (`ConfigurableCustomerReceiptFormatter`)
- **Purpose**: Customer billing and legal compliance
- **Features**:
  - **Clean restaurant header** (no emojis)
  - **Complete billing details**
  - **Tax calculations** per regional rules
  - **Business compliance information**
  - **Multi-language support**
  - **Thermal printer optimized** formatting

## ⚙️ Environment Variables

Override any setting with environment variables:

```bash
# Restaurant Information
export RESTAURANT_NAME="Your Restaurant"
export RESTAURANT_PHONE="+1 234 567 8900"
export RESTAURANT_EMAIL="info@restaurant.com"

# Currency Settings
export CURRENCY_CODE="USD"
export CURRENCY_SYMBOL="$"

# Tax Settings
export TAX_RATE="0.0875"  # 8.75% as decimal

# Regional Settings
export RESTAURANT_REGION="usa"
```

## 🧪 Testing Your Configuration

Test your configuration with sample data:

```bash
python test_thai_receipts.py
```

This will generate sample receipts using your configuration settings.

## 🔧 Advanced Customization

### Custom Preparation Times

Add custom prep time modifiers in `config/cuisine_templates.yaml`:

```yaml
templates:
  your_cuisine:
    prep_time_modifiers:
      "special dish": +5  # adds 5 minutes
      "complex item": +10
```

### Custom Thank You Messages

Customize thank you messages:

```yaml
templates:
  your_cuisine:
    thank_you:
      message: "Your Custom Message!"
      translation: "(Your translation)"
```

### Thermal Printer Optimization

The system is fully optimized for thermal printers:

#### ✅ What Works
- **Pure text formatting** - no emoji dependencies
- **ESC/POS commands** for bold, center, double-width
- **ASCII art separators** (=, -, *)
- **Clean typography** for all languages

#### ❌ What's Removed
- **No emojis** - replaced with ASCII alternatives:
  - `🔥` → `***`
  - `⚠️` → `>>>`
  - `🚨` → `!!!`
  - `✅` → `>>> TEXT <<<`
- **No Unicode symbols** that may not print correctly
- **Minimal headers** to reduce visual clutter

#### 🎯 Thermal Printer Best Practices
```yaml
# Example thermal-optimized language template:
languages:
  de:
    kitchen:
      header: "KÜCHE"           # Not "🍜 KÜCHE 🍜"
      special: "SPEZIELL"       # Printed as ">>> SPEZIELL: ... <<<"
      allergy_warning: "ALLERGIE WARNUNG"  # Printed as "!!! ALLERGIE WARNUNG !!!"
```

## 📁 File Structure

```
config/
├── restaurant_config.yaml      # Your restaurant settings
├── cuisine_templates.yaml      # Cuisine-specific templates
└── regional_settings.yaml      # Regional tax & currency settings

wix_printer_service/
├── config_manager.py          # Configuration management
└── configurable_receipt_formatter.py  # Configurable formatters
```

## 🚨 Troubleshooting

### Configuration Not Loading
1. Check that `config/restaurant_config.yaml` exists
2. Verify YAML syntax with an online validator
3. Check environment variables with `printenv | grep RESTAURANT`

### Wrong Currency Format
1. Verify `CURRENCY_CODE` and `CURRENCY_SYMBOL`
2. Check regional settings in `config/regional_settings.yaml`
3. Ensure `RESTAURANT_REGION` matches your region

### Thermal Printer Issues
1. **Symbols not printing**: System uses only ASCII - no Unicode/emoji issues
2. **Text too wide**: Receipts optimized for 58mm thermal paper
3. **Garbled characters**: Check ESC/POS compatibility (Epson standard supported)
4. **Missing formatting**: Ensure printer supports ESC/POS bold/center commands

### Tax Calculation Issues
1. Check `default_rate` in tax configuration (use decimal: 0.19 for 19%)
2. Verify regional tax settings
3. Test with sample orders to validate calculations

## 💡 Tips for Repository Publishing

When publishing this repository:

1. **Include sample configurations** for common restaurant types
2. **Document all configuration options** with examples
3. **Provide migration guides** for existing users
4. **Test with multiple restaurant types** before release
5. **Include localization files** for different languages

## 🤝 Contributing

To add support for new:
- **Cuisine types**: Update `config/cuisine_templates.yaml`
- **Regions**: Update `config/regional_settings.yaml`
- **Languages**: Add translation files
- **Features**: Extend `ConfigManager` class

---

**Ready to serve any restaurant, anywhere! 🌍🍽️**