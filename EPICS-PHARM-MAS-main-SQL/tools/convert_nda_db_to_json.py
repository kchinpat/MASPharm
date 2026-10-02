import csv
import json
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
UI_DIR = TOOLS_DIR.parent / "UI"

def convert_nda_to_json(input_file, output_file):
    """
    Convert NDA medication database from TSV format to JSON format.
    """
    medications = []
    
    try:
        with open(input_file, 'r', encoding='utf-8') as file:
            # Read the TSV file
            reader = csv.DictReader(file, delimiter='\t')
            
            for row in reader:
                # Convert each row to a dictionary and add to list
                medications.append(dict(row))
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as json_file:
            json.dump(medications, json_file, indent=2, ensure_ascii=False)
        
        print(f"Successfully converted {len(medications)} records to {output_file}")
        return True
        
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found")
        return False
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        return False

def main():
    input_file = TOOLS_DIR / "product.csv"  # Download from the FDA NDC directory and place it in tools/
    output_file = UI_DIR / "fda_product_db.json"
    
    convert_nda_to_json(input_file, output_file)

if __name__ == "__main__":
    main()