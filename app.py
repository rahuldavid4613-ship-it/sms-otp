import asyncio
import requests
import re
import phonenumbers
from phonenumbers import geocoder
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

BOT_TOKEN = "8588637077:AAHR67gqi4-1wJxkr67zERDRQ4roTpLBqno"
bot = Bot(token=BOT_TOKEN)

GROUP_IDS = [
    -1003877594101, 
]

API_URLS = [
    "https://apiotps-theta.vercel.app/api/tempotps?type=sms",
    "https://otps.vercel.app/api/tempotps?type=sms",
    "https://apiotps-theta.vercel.app/api/tempotps?type=numbers",
]

# Store last processed OTPs to avoid duplicates
last_processed = {}

def fetch_latest_otp(api_url):
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        # Debug: Print API response structure
        # print(f"API Response from {api_url}: {data}")
        
        # Check the actual structure of the response
        records = data.get("aaData", [])
        
        if not records:
            print(f"No records found in API response from {api_url}")
            return None
        
        # Get the first (latest) record
        latest = records[0]
        
        # Extract data based on the actual API response structure
        # From your API response, each record has 7 elements:
        # [time, country, number, service, message, "$", 0]
        if len(latest) >= 5:
            return {
                "time": latest[0],        # timestamp
                "country": latest[1],     # country info
                "number": latest[2],      # phone number
                "service": latest[3],     # service name
                "message": latest[4],     # OTP message
            }
        else:
            print(f"Invalid record format from {api_url}: {latest}")
            return None
            
    except Exception as e:
        print(f"Error from {api_url}: {e}")
        return None

def extract_otp(message):
    if not message:
        return "N/A"
    
    # Try to find OTP patterns
    # Look for patterns like: 369-545, 525734, 231608, etc.
    patterns = [
        r'\b\d{3}-\d{3}\b',      # 123-456 format
        r'\b\d{6}\b',            # 123456 format
        r'\b\d{5}\b',            # 12345 format
        r'\b\d{4}\b',            # 1234 format
        r'code\s+(\d{3}-\d{3})', # "code 123-456"
        r'code\s+(\d{6})',       # "code 123456"
        r'code\s+(\d{5})',       # "code 12345"
        r'code\s+(\d{4})',       # "code 1234"
        r'(\d{3}-\d{3})',        # Just 123-456 anywhere
    ]
    
    for pat in patterns:
        match = re.search(pat, str(message))
        if match:
            # Extract the first group if there are groups, otherwise the whole match
            return match.group(1) if match.groups() else match.group(0)
    
    return "N/A"

def mask_number(number_str):
    try:
        # Clean the number string
        number_str = str(number_str).strip()
        
        # Remove any non-digit characters except leading +
        if not number_str.startswith("+"):
            number_str = f"+{number_str}"
        
        # Remove any spaces or dashes
        number_str = re.sub(r'[^\d+]', '', number_str)
        
        length = len(number_str)
        
        if length <= 6:
            return number_str  # Too short to mask
        
        show_first = min(4, length // 3)
        show_last = min(3, length // 4)
        
        if show_first + show_last >= length:
            return number_str
        
        stars = '*' * (length - show_first - show_last)
        return f"{number_str[:show_first]}{stars}{number_str[-show_last:]}"
        
    except Exception as e:
        print(f"Error masking number {number_str}: {e}")
        return f"+{str(number_str)[:15]}"

def get_country_info_from_number(number_str):
    try:
        if not number_str:
            return "Unknown", "🌍"
            
        number_str = str(number_str).strip()
        
        # Clean the number - remove any non-digit characters
        clean_number = re.sub(r'[^\d+]', '', number_str)
        
        if not clean_number.startswith("+"):
            clean_number = f"+{clean_number}"
        
        parsed = phonenumbers.parse(clean_number, None)
        country_name = geocoder.description_for_number(parsed, "en")
        region_code = phonenumbers.region_code_for_number(parsed)

        if region_code and len(region_code) == 2:
            # Generate flag emoji from country code
            base = 127462 - ord("A")
            flag = chr(base + ord(region_code[0])) + chr(base + ord(region_code[1]))
        else:
            flag = "🌍"

        return country_name or "Unknown", flag

    except Exception as e:
        print(f"Error getting country info for {number_str}: {e}")
        return "Unknown", "🌍"

def format_message(record):
    raw = record.get("message", "")
    otp = extract_otp(raw)
    msg = raw.replace("<", "&lt;").replace(">", "&gt;")
    
    country_name, flag = get_country_info_from_number(record.get("number", ""))
    formatted_number = mask_number(record.get("number", ""))
    
    service = record.get("service", "Unknown").lower()
    service_icon = "📱"
    
    if "whatsapp" in service:
        service_icon = "🟢"
    elif "telegram" in service:
        service_icon = "🔵"
    elif "facebook" in service:
        service_icon = "📘"
    elif "microsoft" in service:
        service_icon = "🪟"
    elif "apple" in service:
        service_icon = "🍎"
    
    # Also get country from API if available
    api_country = record.get("country", "").split()[0] if record.get("country") else country_name
    
    return f"""
<b>{flag} New {api_country} {record.get('service', 'Service')} OTP!</b>

<blockquote>🕰 Time: {record.get('time', 'N/A')}</blockquote>
<blockquote>{flag} Country: {country_name}</blockquote>
<blockquote>{service_icon} Service: {record.get('service', 'Unknown')}</blockquote>
<blockquote>📞 Number: {formatted_number}</blockquote>
<blockquote>🔑 OTP: <code>{otp}</code></blockquote>

<blockquote>📩 Full Message:</blockquote>
<pre>{msg[:500]}{'...' if len(msg) > 500 else ''}</pre>

Powered by DIGITAL BYTE 🌌 
Support  ❣️JOHN SNOW ❤️
"""

async def send_to_all_groups(message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Channel", url="https://t.me/+jkki3MY1knAxNGE9"),
            InlineKeyboardButton(text="☎️ Numbers", url="https://t.me/+0fBTwf4k0nJmZThl")
        ],
        [
            InlineKeyboardButton(text="👨‍💻 Developer", url="https://t.me/digital_byte_bot"),
            InlineKeyboardButton(text="🚀 YouTube", url="https://youtube.com/@johnsnow-k6e?si=tH9xnOPu10U4QWDx")
        ]
    ])

    for group in GROUP_IDS:
        try:
            await bot.send_message(
                chat_id=group,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard
            )
            print(f"[{datetime.now()}] Successfully sent to group {group}")
        except Exception as e:
            print(f"Error sending to group {group}: {e}")

async def api_worker(api_url):
    print(f"[STARTED] Worker for {api_url}")
    
    # Initialize last_processed for this API
    if api_url not in last_processed:
        last_processed[api_url] = set()

    while True:
        try:
            otp_record = fetch_latest_otp(api_url)
            
            if otp_record:
                # Create a unique identifier for this OTP
                # Use number + message hash to avoid duplicates
                otp_id = f"{otp_record.get('number', '')}:{hash(otp_record.get('message', '')) % 1000000}"
                
                if otp_id not in last_processed[api_url]:
                    # Add to processed set
                    last_processed[api_url].add(otp_id)
                    
                    # Keep only last 1000 processed IDs to avoid memory issues
                    if len(last_processed[api_url]) > 1000:
                        # Convert to list and remove oldest (first) element
                        last_list = list(last_processed[api_url])
                        last_processed[api_url] = set(last_list[-1000:])
                    
                    msg = format_message(otp_record)
                    await send_to_all_groups(msg)
                    
                    print(f"[{datetime.now()}] Sent new OTP from {otp_record.get('number', 'N/A')} | Service: {otp_record.get('service', 'N/A')} | API: {api_url}")
                else:
                    print(f"[{datetime.now()}] OTP already processed: {otp_record.get('number', 'N/A')}")
            
            # Wait before checking again
            await asyncio.sleep(5)  # Increased to 5 seconds to avoid rate limiting
            
        except Exception as e:
            print(f"Error in worker for {api_url}: {e}")
            await asyncio.sleep(10)  # Wait longer on error

async def main():
    print("Starting multi-API, multi-group OTP bot...")
    print("=" * 50)
    
    # Initialize all API workers
    tasks = []
    for api in API_URLS:
        task = asyncio.create_task(api_worker(api))
        tasks.append(task)
        await asyncio.sleep(1)  # Stagger the starts
    
    print(f"Started {len(tasks)} API workers")
    print("Bot is running. Press Ctrl+C to stop.")
    print("=" * 50)
    
    # Keep all tasks running
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
