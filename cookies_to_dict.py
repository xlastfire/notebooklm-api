import json
import sys

def parse_netscape_cookies(cookie_text):
    cookie_dict = {}
    lines = cookie_text.strip().splitlines()
    
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
            
        parts = line.split('\t')
        if len(parts) >= 7:
            name = parts[5].strip()
            value = parts[6].strip()
            cookie_dict[name] = value
        elif len(line.split()) >= 2:
            temp_parts = line.split()
            cookie_dict[temp_parts[-2]] = temp_parts[-1]
            
    return cookie_dict

def main():
    file_name = input("Enter the file name (without .json): ").strip() + '.json'
    
    print("\n[!] Paste your cookies below.")
    print("[!] After pasting, press Ctrl+Z (Windows) or Ctrl+D (Mac/Linux) and then ENTER:")
    
    raw_cookies = sys.stdin.read()

    if not raw_cookies.strip():
        print("No cookies found!")
        return

    cooked = parse_netscape_cookies(raw_cookies)

    with open(file_name, 'w', encoding='utf-8') as file:
        json.dump(cooked, file, ensure_ascii=False, indent=4)
        
    print(f"\n[+] Success! {len(cooked)} cookies saved to {file_name}")
        
if __name__ == "__main__":
    main()