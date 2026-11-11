from __future__ import annotations
import re
from dataclasses import dataclass
@dataclass(frozen=True)
class CalculationResult:
    metric: str
    value: float | None
    formula: str
    unit: str
    status: str
    limitation: str | None = None
_CURRENCY={"inr":"INR","₹":"INR","rs":"INR","usd":"USD","$":"USD","eur":"EUR","€":"EUR","gbp":"GBP","£":"GBP"}
_SCALE={"":1.0,"unit":1.0,"units":1.0,"thousand":1e3,"thousands":1e3,"lakh":1e5,"lakhs":1e5,"million":1e6,"millions":1e6,"crore":1e7,"crores":1e7,"billion":1e9,"billions":1e9}
def _unit_parts(unit:str):
    text=unit.strip().lower().replace("₹"," inr ").replace("$"," usd ").replace("€"," eur ").replace("£"," gbp ")
    currency=next((code for token,code in _CURRENCY.items() if token.isascii() and re.search(rf"\b{re.escape(token)}\b",text)),None)
    scale=next((v for k,v in _SCALE.items() if k and re.search(rf"\b{re.escape(k)}\b",text)),1.0)
    if "percent" in text or "%" in text: return "PERCENT",1.0
    if currency is None and scale!=1.0: currency="UNSPECIFIED_CURRENCY"
    return currency,scale
def unit_scale(unit:str)->float: return _unit_parts(unit)[1] or 1.0
def validate_same_unit(first_unit:str,second_unit:str)->bool:
    a,sa=_unit_parts(first_unit); b,sb=_unit_parts(second_unit)
    return a==b and sa is not None and sb is not None
def convert_amount(value:float,from_unit:str,to_unit:str)->float:
    if not validate_same_unit(from_unit,to_unit): raise ValueError(f"Incompatible units: {from_unit!r} and {to_unit!r}")
    return value*unit_scale(from_unit)/unit_scale(to_unit)
def yoy_growth(current:float,prior:float,unit:str="%")->CalculationResult:
    if prior==0: return CalculationResult("year-over-year growth",None,"(current - prior) / prior × 100",unit,"abstained","The comparative denominator is zero.")
    return CalculationResult("year-over-year growth",round((current-prior)/prior*100,4),f"({current} - {prior}) / {prior} × 100",unit,"calculated")
def absolute_change(current:float,prior:float,unit:str="reported units")->CalculationResult:
    return CalculationResult("absolute change",round(current-prior,4),f"{current} - {prior}",unit,"calculated")
_AMOUNT_RE=re.compile(r"(?P<currency>INR|USD|EUR|GBP|₹|\$|€|£)?\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<scale>crores|crore|lakhs|lakh|millions|million|billions|billion|thousands|thousand)?",re.I)
def parse_amounts(text:str):
    out=[]
    for m in _AMOUNT_RE.finditer(text):
        currency=(m.group("currency") or "").upper().replace("₹","INR").replace("$","USD").replace("€","EUR").replace("£","GBP")
        scale=(m.group("scale") or "").lower(); unit=" ".join(x for x in (currency,scale) if x).strip() or "reported units"
        out.append((float(m.group("number").replace(",","")),unit))
    return out
