from __future__ import annotations
from typing import List, Dict, Any
import re


def extract_line_items_from_table(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Post-process a messy invoice table to extract clean line items.
    
    Looks for the charges section (after "Size/Type Charge Description..." header)
    and splits merged rows.
    
    Returns list of line items with keys:
    - description
    - quantity
    - rate
    - currency
    - amount_vnd
    """
    rows = table.get("rows", [])
    line_items: List[Dict[str, Any]] = []
    
    # Find the header row (contains "Charge Description")
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0] and "Charge Description" in str(row[0]):
            header_idx = i
            break
    
    if header_idx is None:
        return []  # No charge section found
    
    # Process rows after the header until we hit totals
    for i in range(header_idx + 1, len(rows)):
        cell = rows[i][0]  # main content is in column 0
        if not cell or not isinstance(cell, str):
            continue
        
        # Stop when we hit totals/exchange rows
        if any(kw in cell.lower() for kw in ["rate of exchange", "total excluding", "vat applied"]):
            break
        
        # Split by newlines (handles merged rows)
        lines = [ln.strip() for ln in cell.split("\n") if ln.strip()]
        
        for line in lines:
            # Parse the line (example pattern, adjust based on your invoices)
            # Typical format: "40RH C Description F1 1UNI 6,050,000.00 VND 6,050,000.00"
            item = parse_charge_line(line)
            if item:
                # Try to get amount from column 2 (if available)
                amount_col = rows[i][2] if len(rows[i]) > 2 and rows[i][2] else None
                if amount_col and isinstance(amount_col, str):
                    amounts = [a.strip() for a in amount_col.split("\n") if a.strip()]
                    # Match line index to amount (heuristic)
                    line_idx = lines.index(line)
                    if line_idx < len(amounts):
                        item["amount_vnd"] = amounts[line_idx]
                
                line_items.append(item)
    
    return line_items


def parse_charge_line(line: str) -> Dict[str, Any] | None:
    """
    Parse a single charge line.
    Example: "40RH C Phí xếp hàng tại nơi xếp hàng F1 1UNI 6,050,000.00 VND 6,050,000.00"
    
    Returns dict with description, qty, rate, currency, or None if not parseable.
    """
    # Remove leading container type/code (40RH, C, etc.)
    line = re.sub(r"^(40RH|20GP|C|F1)\s+", "", line).strip()
    
    # Try to extract known patterns
    # Pattern: description ... <qty><unit> <rate> <currency> <amount>
    # This is heuristic; tune based on your invoices
    
    # Simple approach: find currency keywords
    currencies = ["USD", "VND", "EUR", "UNI"]  # UNI is unit, treat as currency placeholder
    
    parts = line.split()
    description_parts = []
    qty = None
    rate = None
    currency = None
    
    for i, part in enumerate(parts):
        if part in currencies:
            currency = part
            # Try to extract rate before currency
            if i > 0:
                try:
                    rate = parts[i - 1].replace(",", "")
                    float(rate)  # validate
                except:
                    rate = None
            # Description is everything before rate
            if rate and i > 1:
                description_parts = parts[:i - 1]
            else:
                description_parts = parts[:i]
            break
        else:
            description_parts.append(part)
    
    if not description_parts:
        return None
    
    return {
        "description": " ".join(description_parts),
        "quantity": qty or "1",  # default
        "rate": rate or "",
        "currency": currency or "",
        "amount_vnd": "",  # filled from column 2
    }