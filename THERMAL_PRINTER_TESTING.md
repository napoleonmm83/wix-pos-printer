# 🖨️ Thermal Printer Testing Guide

## 📋 Pre-Testing Checklist

### Hardware Requirements
- [ ] Thermal printer connected via USB
- [ ] Printer power cable connected
- [ ] Thermal paper loaded (58mm width recommended)
- [ ] Printer drivers installed (if required)

### Software Requirements
- [ ] `python-escpos` library installed
- [ ] Printer permissions configured (`/dev/usb/lp0` or similar)
- [ ] System recognizes printer (`lsusb` shows device)

## 🧪 Test Scenarios

### 1. Kitchen Receipt Tests

**Test Case 1.1: Basic Kitchen Receipt**
```python
# Test with minimal order
python test_kitchen_header.py
```

**Expected Output:**
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
2x Som Tam

================================
*** FRISCH ZUBEREITEN ***
```

**Verify:**
- [ ] No question marks or garbled characters
- [ ] Bold formatting works for headers
- [ ] Separators print correctly (=, -, *)
- [ ] Text is readable at normal kitchen distance
- [ ] Paper cuts cleanly

**Test Case 1.2: Special Instructions**
```python
# Create order with special notes and allergies
order_with_notes = Order(
    items=[
        OrderItem(name="Pad Thai", quantity=1, notes="Extra scharf, keine Nüsse"),
    ]
)
```

**Expected Output:**
```
1x Pad Thai
>>> SPEZIELL: Extra scharf, keine Nüsse <<<
!!! ALLERGIE WARNUNG !!!
```

**Verify:**
- [ ] Special instructions clearly visible
- [ ] Allergy warnings stand out
- [ ] ASCII art (`>>>`, `!!!`) prints correctly

### 2. Service Receipt Tests

**Test Case 2.1: Pickup Receipt**
```python
# Test pickup service
order.order_type = "pickup"
service_formatter.format_receipt(order)
```

**Expected Output:**
```
THAI RESTAURANT - ABHOLUNG
Bereit zur Abholung
================================
BESTELLUNG #10033
...
>>> BEREIT ZUR ABHOLUNG <<<
```

**Verify:**
- [ ] Restaurant name and service type clear
- [ ] Customer info readable
- [ ] Action prompts (`>>>`) stand out

**Test Case 2.2: Delivery Receipt**
```python
# Test delivery service with address
order.order_type = "delivery"
```

**Verify:**
- [ ] Delivery address prints clearly
- [ ] Multi-line addresses formatted correctly
- [ ] Contact information visible

### 3. Customer Receipt Tests

**Test Case 3.1: Legal Compliance**
```python
customer_formatter.format_receipt(order)
```

**Verify:**
- [ ] Restaurant header clean (no emojis)
- [ ] All required business info present
- [ ] Tax calculations display correctly
- [ ] Currency symbols print properly (€, $, CHF)
- [ ] Legal footer text included

### 4. Multi-Language Tests

**Test Case 4.1: German Language**
```yaml
# config/restaurant_config.yaml
localization:
  language: "de"
```

**Test Case 4.2: English Language**
```yaml
localization:
  language: "en"
```

**Expected Differences:**
- German: "KÜCHE", "BESTELLUNG", "SPEZIELL"
- English: "KITCHEN", "ORDER", "SPECIAL"

**Verify:**
- [ ] All text translates correctly
- [ ] No fallback to German when English expected
- [ ] Formatting remains consistent

### 5. Edge Case Tests

**Test Case 5.1: Missing Data**
```python
# Test with minimal/missing order data
empty_order = Order(
    items=[],
    wix_order_id="",
    customer_name=None
)
```

**Verify:**
- [ ] System doesn't crash
- [ ] Fallback values used appropriately
- [ ] Receipt still printable

**Test Case 5.2: Long Text**
```python
# Test with very long item names and notes
long_item = OrderItem(
    name="Very Long Thai Dish Name That Might Wrap",
    notes="Very long special instructions that might cause formatting issues on thermal printer"
)
```

**Verify:**
- [ ] Long text wraps properly
- [ ] No text cutoff
- [ ] Formatting preserved

## 🔍 Troubleshooting

### Common Issues

**Issue: Question marks (?) instead of characters**
- **Cause**: Unicode characters not supported
- **Solution**: Check for remaining emojis in code
- **Test**: Search codebase for Unicode characters

**Issue: Text too wide for paper**
- **Cause**: Line length exceeds 32-48 characters (depends on printer)
- **Solution**: Check ESCPOSFormatter line width settings
- **Test**: Print test pattern with known character counts

**Issue: Bold/formatting not working**
- **Cause**: Printer doesn't support ESC/POS commands
- **Solution**: Test with different printer or update drivers
- **Test**: Send raw ESC/POS commands

**Issue: Paper not cutting**
- **Cause**: Cut command not supported or wrong command
- **Solution**: Check `ESCPOSFormatter.CUT_PARTIAL` implementation
- **Test**: Try different cut commands

### Debugging Commands

```bash
# Check printer connection
lsusb | grep -i printer

# Test basic printing
echo "Hello World" > /dev/usb/lp0

# Check ESC/POS support
python -c "
from escpos.printer import Usb
p = Usb(0x04b8, 0x0e32)  # Your printer's vendor:product ID
p.text('TEST\n')
p.cut()
"
```

## ✅ Test Completion Checklist

### Hardware Verification
- [ ] All three receipt types print without errors
- [ ] No question marks or garbled characters
- [ ] Bold formatting works correctly
- [ ] Paper cuts cleanly
- [ ] Text is readable from normal distance

### Software Verification
- [ ] All language templates work
- [ ] Fallback values work when data missing
- [ ] Long text handles gracefully
- [ ] Special characters (€, $, ü, ä, ö) print correctly
- [ ] System recovers from printer errors

### User Experience
- [ ] Kitchen staff can read receipts quickly
- [ ] Service staff have all needed customer info
- [ ] Customer receipts look professional
- [ ] Receipt content matches expectations

## 📊 Performance Tests

### Speed Test
```bash
time python -c "
# Print 10 receipts in sequence
for i in range(10):
    formatter.format_receipt(test_order)
    printer.print_receipt(receipt)
"
```

**Target**: < 5 seconds per receipt including printing time

### Stress Test
```bash
# Test continuous printing for 1 hour
python stress_test_printer.py --duration=3600
```

**Verify:**
- [ ] No memory leaks
- [ ] No print quality degradation
- [ ] No thermal printer overheating

## 📝 Test Results Template

```
Date: ___________
Printer Model: ___________
Paper Width: ___________
Connection: USB/Network/Bluetooth

Kitchen Receipt:    ✅ ❌ Notes: ___________
Service Receipt:    ✅ ❌ Notes: ___________
Customer Receipt:   ✅ ❌ Notes: ___________

German Language:    ✅ ❌ Notes: ___________
English Language:   ✅ ❌ Notes: ___________

Performance:        ✅ ❌ Notes: ___________
Edge Cases:         ✅ ❌ Notes: ___________

Overall Result:     ✅ Ready for Production
                   ❌ Issues found (see notes)
```