"""
Configuration Manager for customizable receipt formatting.
Supports multiple cuisines, regions, and business types.
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CurrencyConfig:
    code: str = "EUR"
    symbol: str = "€"
    decimal_places: int = 2
    format_template: str = "{amount:.2f}{symbol}"

    def format_amount(self, amount: float) -> str:
        return self.format_template.format(amount=amount, symbol=self.symbol)


@dataclass
class TaxConfig:
    default_rate: float = 0.19
    food_rate: Optional[float] = None
    beverage_rate: Optional[float] = None
    service_rate: Optional[float] = None
    show_breakdown: bool = True
    business_id_format: str = "Business ID: XXX"
    footer_text: str = ""

    def get_rate_for_item_type(self, item_type: str = "food") -> float:
        """Get tax rate for specific item type."""
        if item_type == "food" and self.food_rate is not None:
            return self.food_rate
        elif item_type == "beverage" and self.beverage_rate is not None:
            return self.beverage_rate
        elif item_type == "service" and self.service_rate is not None:
            return self.service_rate
        return self.default_rate


@dataclass
class RestaurantConfig:
    name: str = "Restaurant"
    address_lines: List[str] = field(default_factory=list)
    phone: str = ""
    email: str = ""
    website: str = ""


@dataclass
class BrandingConfig:
    cuisine_type: str = "generic"
    primary_emoji: str = "🍽️"
    cuisine_emojis: List[str] = field(default_factory=lambda: ["🍴"])
    service_emojis: Dict[str, str] = field(default_factory=lambda: {
        "pickup": "📦",
        "delivery": "🚗"
    })
    thank_you_message: str = "Vielen Dank!"
    thank_you_translation: str = "(Thank you)"


@dataclass
class LanguageTemplates:
    kitchen: Dict[str, str] = field(default_factory=dict)
    service: Dict[str, str] = field(default_factory=dict)
    customer: Dict[str, str] = field(default_factory=dict)
    common: Dict[str, str] = field(default_factory=dict)


@dataclass
class LocalizationConfig:
    language: str = "de"
    currency: CurrencyConfig = field(default_factory=CurrencyConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
    text_templates: LanguageTemplates = field(default_factory=LanguageTemplates)


class ConfigManager:
    """Manages configuration for customizable receipt formatting."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory containing config files. Defaults to ./config/
        """
        self.config_dir = Path(config_dir or "config")

        # Default configurations
        self.restaurant = RestaurantConfig()
        self.branding = BrandingConfig()
        self.localization = LocalizationConfig()

        # Load configurations
        self._load_configurations()

    def _load_configurations(self):
        """Load all configuration files."""
        try:
            # Load main restaurant config
            self._load_restaurant_config()

            # Load cuisine template
            self._load_cuisine_template()

            # Load regional settings
            self._load_regional_settings()

            # Load language templates
            self._load_language_templates()

            # Override with environment variables
            self._load_env_overrides()

            logger.info(f"Configuration loaded: {self.restaurant.name} ({self.branding.cuisine_type})")

        except Exception as e:
            logger.warning(f"Error loading configuration: {e}. Using defaults.")

    def _load_restaurant_config(self):
        """Load main restaurant configuration."""
        config_file = self.config_dir / "restaurant_config.yaml"
        if not config_file.exists():
            logger.info("No restaurant_config.yaml found, using defaults")
            return

        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Restaurant info
        restaurant_data = config.get('restaurant', {})
        self.restaurant.name = restaurant_data.get('name', self.restaurant.name)
        self.restaurant.phone = restaurant_data.get('phone', self.restaurant.phone)
        self.restaurant.email = restaurant_data.get('email', self.restaurant.email)

        # Address
        address_data = restaurant_data.get('address', [])
        if isinstance(address_data, list):
            self.restaurant.address_lines = address_data
        elif isinstance(address_data, str):
            self.restaurant.address_lines = [address_data]

        # Branding
        branding_data = config.get('branding', {})
        self.branding.cuisine_type = branding_data.get('cuisine_type', self.branding.cuisine_type)

        # Currency
        currency_data = config.get('currency', {})
        self.localization.currency.code = currency_data.get('code', self.localization.currency.code)
        self.localization.currency.symbol = currency_data.get('symbol', self.localization.currency.symbol)

        # Tax
        tax_data = config.get('tax', {})
        self.localization.tax.default_rate = tax_data.get('default_rate', self.localization.tax.default_rate)
        self.localization.tax.business_id_format = tax_data.get('business_id', self.localization.tax.business_id_format)

    def _load_cuisine_template(self):
        """Load cuisine-specific template."""
        templates_file = self.config_dir / "cuisine_templates.yaml"
        if not templates_file.exists():
            return

        with open(templates_file, 'r', encoding='utf-8') as f:
            templates = yaml.safe_load(f)

        cuisine_template = templates.get('templates', {}).get(self.branding.cuisine_type)
        if not cuisine_template:
            logger.warning(f"No template found for cuisine type: {self.branding.cuisine_type}")
            return

        # Apply template
        self.branding.primary_emoji = cuisine_template.get('primary_emoji', self.branding.primary_emoji)
        self.branding.cuisine_emojis = cuisine_template.get('cuisine_emojis', self.branding.cuisine_emojis)

        service_emojis = cuisine_template.get('service_emojis', {})
        self.branding.service_emojis.update(service_emojis)

        # Thank you message
        thank_you = cuisine_template.get('thank_you', {})
        self.branding.thank_you_message = thank_you.get('message', self.branding.thank_you_message)
        self.branding.thank_you_translation = thank_you.get('translation', self.branding.thank_you_translation)

    def _load_regional_settings(self):
        """Load region-specific settings."""
        # Try to determine region from environment or config
        region = os.getenv('RESTAURANT_REGION', 'switzerland')  # Default to Switzerland

        regional_file = self.config_dir / "regional_settings.yaml"
        if not regional_file.exists():
            return

        with open(regional_file, 'r', encoding='utf-8') as f:
            settings = yaml.safe_load(f)

        region_config = settings.get('regions', {}).get(region)
        if not region_config:
            logger.warning(f"No regional settings found for: {region}")
            return

        # Currency
        currency_data = region_config.get('currency', {})
        self.localization.currency.code = currency_data.get('code', self.localization.currency.code)
        self.localization.currency.symbol = currency_data.get('symbol', self.localization.currency.symbol)
        self.localization.currency.format_template = currency_data.get('format', self.localization.currency.format_template)

        # Tax
        tax_data = region_config.get('tax', {})
        self.localization.tax.food_rate = tax_data.get('food_rate')
        self.localization.tax.beverage_rate = tax_data.get('beverage_rate')
        self.localization.tax.default_rate = tax_data.get('standard_rate', self.localization.tax.default_rate)
        self.localization.tax.business_id_format = tax_data.get('business_id_format', self.localization.tax.business_id_format)

        # Legal
        legal_data = region_config.get('legal', {})
        self.localization.tax.footer_text = legal_data.get('footer_text', self.localization.tax.footer_text)

    def _load_language_templates(self):
        """Load language templates for the configured language."""
        templates_file = self.config_dir / "language_templates.yaml"
        if not templates_file.exists():
            logger.warning("No language_templates.yaml found, using default templates")
            return

        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                templates = yaml.safe_load(f)

            language_data = templates.get('languages', {}).get(self.localization.language)
            if not language_data:
                logger.warning(f"No templates found for language: {self.localization.language}")
                return

            # Load templates for each section
            self.localization.text_templates.kitchen = language_data.get('kitchen', {})
            self.localization.text_templates.service = language_data.get('service', {})
            self.localization.text_templates.customer = language_data.get('customer', {})
            self.localization.text_templates.common = language_data.get('common', {})

            logger.info(f"Language templates loaded for: {self.localization.language}")

        except Exception as e:
            logger.warning(f"Error loading language templates: {e}")

    def get_text(self, section: str, key: str, default: str = "") -> str:
        """Get localized text for a specific section and key."""
        if section == 'kitchen':
            return self.localization.text_templates.kitchen.get(key, default)
        elif section == 'service':
            return self.localization.text_templates.service.get(key, default)
        elif section == 'customer':
            return self.localization.text_templates.customer.get(key, default)
        elif section == 'common':
            return self.localization.text_templates.common.get(key, default)
        else:
            logger.warning(f"Unknown text section: {section}")
            return default

    def _load_env_overrides(self):
        """Load environment variable overrides."""
        # Restaurant overrides
        if os.getenv('RESTAURANT_NAME'):
            self.restaurant.name = os.getenv('RESTAURANT_NAME')

        if os.getenv('RESTAURANT_PHONE'):
            self.restaurant.phone = os.getenv('RESTAURANT_PHONE')

        if os.getenv('RESTAURANT_EMAIL'):
            self.restaurant.email = os.getenv('RESTAURANT_EMAIL')

        # Currency overrides
        if os.getenv('CURRENCY_CODE'):
            self.localization.currency.code = os.getenv('CURRENCY_CODE')

        if os.getenv('CURRENCY_SYMBOL'):
            self.localization.currency.symbol = os.getenv('CURRENCY_SYMBOL')

        # Tax overrides
        if os.getenv('TAX_RATE'):
            try:
                self.localization.tax.default_rate = float(os.getenv('TAX_RATE'))
            except ValueError:
                logger.warning("Invalid TAX_RATE environment variable")

    def get_prep_time_modifier(self, dish_name: str) -> int:
        """Get preparation time modifier for specific dish."""
        # Load from cuisine template if available
        templates_file = self.config_dir / "cuisine_templates.yaml"
        if not templates_file.exists():
            return 0

        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                templates = yaml.safe_load(f)

            cuisine_template = templates.get('templates', {}).get(self.branding.cuisine_type, {})
            modifiers = cuisine_template.get('prep_time_modifiers', {})

            # Check for exact match first, then partial matches
            dish_lower = dish_name.lower()

            # Exact match
            if dish_lower in modifiers:
                return modifiers[dish_lower]

            # Partial match
            for dish_key, modifier in modifiers.items():
                if dish_key in dish_lower:
                    return modifier

            return 0

        except Exception as e:
            logger.warning(f"Error loading prep time modifiers: {e}")
            return 0

    def create_sample_config(self):
        """Create sample configuration files for new users."""
        sample_config = {
            'restaurant': {
                'name': 'Your Restaurant Name',
                'address': [
                    'Your Street Address',
                    'Your City, Postal Code',
                    'Your Country'
                ],
                'phone': '+XX XXX XXX XXXX',
                'email': 'info@your-restaurant.com'
            },
            'branding': {
                'cuisine_type': 'generic',  # Options: thai, italian, mexican, german, generic
            },
            'currency': {
                'code': 'EUR',
                'symbol': '€'
            },
            'tax': {
                'default_rate': 0.19,  # 19% VAT
                'business_id': 'Your Business ID'
            },
            'localization': {
                'language': 'de'  # de, en, fr, it
            }
        }

        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)

        # Write sample config
        config_file = self.config_dir / "restaurant_config.yaml"
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(sample_config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Sample configuration created at: {config_file}")
        return config_file


# Global config instance
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    return config_manager


def reload_config():
    """Reload configuration from files."""
    global config_manager
    config_manager = ConfigManager()
    return config_manager