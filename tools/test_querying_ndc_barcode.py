import json
import sys
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent.parent / "UI"

with open(UI_DIR / "fda_product_db_indexed.json", "r") as f:
    fda_product_db_indexed:dict = json.load(f)

def query_ndc_code(barcode_str:str):
    """
    Algorithm for querying ndc code
    start with barcode
    359651029282
    Remove Starting and ending digits
    5965102928
    
    According to https://www.drugs.com/ndc.html,
    there are formats: 4-4-2, 5-3-2, or 5-4-1

    4-4-2: 5965-1029-28
    5-3-2: 59651-029-28
    5-4-1: 59651-0292-8
    """
    print(barcode_str)

    # remove first_and_last characters
    barcode_str = barcode_str[1:-1]

    print("Remove Staring and ending digits")
    print(barcode_str)

    format_4_4_2 = (barcode_str[0:4], barcode_str[4:8], barcode_str[8:10])
    format_5_3_2 = (barcode_str[0:5], barcode_str[5:8], barcode_str[8:10])
    format_5_4_1 = (barcode_str[0:5], barcode_str[5:9], barcode_str[9:10])

    print(f"4-4-2: {format_4_4_2[0]}-{format_4_4_2[1]}-{format_4_4_2[2]}")
    print(f"5-3-2: {format_5_3_2[0]}-{format_5_3_2[1]}-{format_5_3_2[2]}")
    print(f"5-4-1: {format_5_4_1[0]}-{format_5_4_1[1]}-{format_5_4_1[2]}")

    fda_medication_info = fda_product_db_indexed.get(f"{format_4_4_2[0]}-{format_4_4_2[1]}")
    if not fda_medication_info:
        fda_medication_info = fda_product_db_indexed.get(f"{format_5_3_2[0]}-{format_5_3_2[1]}")
    if not fda_medication_info:
        fda_medication_info = fda_product_db_indexed.get(f"{format_5_4_1[0]}-{format_5_4_1[1]}") 
    print(fda_medication_info)
    if not fda_medication_info:
        return None
    return fda_medication_info

if __name__ == "__main__":
    print(query_ndc_code("360505082919"))
    print(query_ndc_code("370700113844"))
    print(query_ndc_code("305559026588"))
    print(query_ndc_code("370700119846"))
    print(query_ndc_code("359651029282"))
    print(query_ndc_code("359651029282"))
    print(query_ndc_code("068180840730"))
    print(query_ndc_code("068180840730"))
    print(query_ndc_code("005485701000"))
