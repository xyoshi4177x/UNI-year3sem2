# server/storage.py
import csv
import random
from decimal import Decimal, InvalidOperation
from typing import Dict, Tuple


class ElementStore:
    def __init__(self):
        # Store as: lower_name -> (CanonicalName, Decimal weight)
        self.elements: Dict[str, Tuple[str, Decimal]] = {}

    def load_from_csv(self, csv_path: str):
        """Load elements from CSV file into memory."""
        self.elements.clear()
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                name = row[0].strip()
                weight_str = row[1].strip()
                try:
                    weight = Decimal(weight_str)
                    self.elements[name.lower()] = (name, weight)
                except Exception:
                    continue  # skip bad lines

    def get_weight(self, name: str) -> Decimal:
        """Return weight for element name or raise KeyError."""
        key = name.lower()
        if key not in self.elements:
            raise KeyError(f"Element '{name}' not found")
        return self.elements[key][1]

    def get_quantity(self, name: str, student_id: int) -> int:
        """Simulate quantity using formula."""
        weight = self.get_weight(name)
        multiplier = random.randint(1, 10)
        quantity = multiplier * student_id * weight
        return int(round(quantity, 0))

    def add_element(self, name: str, weight: str):
        """Add new element if not duplicate. Weight is a string to avoid float rounding."""
        key = name.lower()
        if key in self.elements:
            raise ValueError(f"Duplicate element '{name}'")
        try:
            w = Decimal(weight)
        except (InvalidOperation, TypeError):
            raise ValueError("Invalid weight")
        if w <= 0:
            raise ValueError("Invalid weight")
        self.elements[key] = (name, w)
