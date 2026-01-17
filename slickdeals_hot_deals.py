#!/usr/bin/env python3
"""
Slickdeals Hot Deals Daily Email
================================
Scrapes Slickdeals for deals with the fire emoji (🔥) and sends a daily email digest.
Configured for GitHub Actions - email settings come from repository secrets.
"""

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import re
import os

# ============================================
# CONFIGURATION - FROM ENVIRONMENT VARIABLES
# ============================================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")

# ============================================
# SCRAPING FUNCTIONS
# ============================================

def get_hot_deals():
    """Scrape Slickdeals frontpage for deals marked as hot (fire emoji)."""
    
    url = "https://slickdeals.net/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching Slickdeals: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    hot_deals = []
    
    # Find deal cards - Slickdeals uses various selectors
    deal_containers = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(deal|fpItem|gridItem)', re.I))
    
    for container in deal_containers:
        # Check for fire emoji or "hot" indicator
        container_text = container.get_text()
        has_fire = '🔥' in container_text or 'Popular' in container_text or 'Hot' in container_text
        
        # Also check for fire icon classes
        fire_icon = container.find(class_=re.compile(r'(fire|hot|flame|popular)', re.I))
        if fire_icon:
            has_fire = True
            
        # Check for the specific "dealTilePopular" or similar hot indicators
        if container.find(class_=re.compile(r'(popular|trending)', re.I)):
            has_fire = True
        
        if not has_fire:
            continue
            
        # Extract deal info
        deal = extract_deal_info(container)
        if deal and deal.get('title'):
            hot_deals.append(deal)
    
    # Also check the frontpage deals grid specifically
    fp_deals = soup.find_all(class_=re.compile(r'(fpDeal|frontpageDeal)', re.I))
    for fp in fp_deals:
        if '🔥' in fp.get_text() or fp.find(class_=re.compile(r'fire|hot|popular', re.I)):
            deal = extract_deal_info(fp)
            if deal and deal.get('title') and deal not in hot_deals:
                hot_deals.append(deal)
    
    # Remove duplicates based on title
    seen_titles = set()
    unique_deals = []
    for deal in hot_deals:
        if deal['title'] not in seen_titles:
            seen_titles.add(deal['title'])
            unique_deals.append(deal)
    
    return unique_deals


def extract_deal_info(container):
    """Extract deal information from a container element."""
    deal = {
        'title': '',
        'price': '',
        'store': '',
        'link': '',
        'votes': ''
    }
    
    # Find title - usually in an anchor or heading
    title_elem = (
        container.find('a', class_=re.compile(r'(title|dealTitle|itemTitle)', re.I)) or
        container.find(['h2', 'h3', 'h4']) or
        container.find('a', href=re.compile(r'/f/'))
    )
    
    if title_elem:
        deal['title'] = title_elem.get_text(strip=True)
        if title_elem.get('href'):
            href = title_elem['href']
            if not href.startswith('http'):
                href = 'https://slickdeals.net' + href
            deal['link'] = href
    
    # Find price
    price_elem = container.find(class_=re.compile(r'(price|dealPrice)', re.I))
    if price_elem:
        deal['price'] = price_elem.get_text(strip=True)
    else:
        # Look for dollar amounts in text
        text = container.get_text()
        price_match = re.search(r'\$[\d,]+\.?\d*', text)
        if price_match:
            deal['price'] = price_match.group()
    
    # Find store name
    store_elem = container.find(class_=re.compile(r'(store|merchant)', re.I))
    if store_elem:
        deal['store'] = store_elem.get_text(strip=True)
    
    # Find vote count
    vote_elem = container.find(class_=re.compile(r'(vote|score|thumb)', re.I))
    if vote_elem:
        deal['votes'] = vote_elem.get_text(strip=True)
    
    return deal


# ============================================
# EMAIL FUNCTIONS
# ============================================

def create_email_html(deals):
    """Create a nicely formatted HTML email with the hot deals."""
    
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 10px; }}
            .deal {{ background: #f9f9f9; border-left: 4px solid #e74c3c; padding: 15px; margin: 15px 0; }}
            .deal-title {{ font-size: 16px; font-weight: bold; color: #2c3e50; }}
            .deal-title a {{ color: #2980b9; text-decoration: none; }}
            .deal-title a:hover {{ text-decoration: underline; }}
            .deal-meta {{ color: #7f8c8d; font-size: 14px; margin-top: 8px; }}
            .price {{ color: #27ae60; font-weight: bold; font-size: 18px; }}
            .store {{ color: #8e44ad; }}
            .votes {{ color: #e67e22; }}
            .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #95a5a6; font-size: 12px; }}
            .no-deals {{ text-align: center; padding: 40px; color: #7f8c8d; }}
        </style>
    </head>
    <body>
        <h1>🔥 Slickdeals Hot Deals</h1>
        <p style="color: #7f8c8d;">{date_str}</p>
    """
    
    if not deals:
        html += """
        <div class="no-deals">
            <p>No hot deals found today. Check back tomorrow!</p>
        </div>
        """
    else:
        html += f"<p><strong>{len(deals)} hot deal{'s' if len(deals) != 1 else ''} found:</strong></p>"
        
        for deal in deals:
            html += f"""
            <div class="deal">
                <div class="deal-title">
                    🔥 <a href="{deal['link']}" target="_blank">{deal['title']}</a>
                </div>
                <div class="deal-meta">
            """
            
            if deal['price']:
                html += f'<span class="price">{deal["price"]}</span> '
            if deal['store']:
                html += f'<span class="store">@ {deal["store"]}</span> '
            if deal['votes']:
                html += f'<span class="votes">({deal["votes"]} votes)</span>'
                
            html += """
                </div>
            </div>
            """
    
    html += """
        <div class="footer">
            <p>This email was automatically generated by your Slickdeals Hot Deals script.</p>
            <p>Visit <a href="https://slickdeals.net">Slickdeals.net</a> for more deals.</p>
        </div>
    </body>
    </html>
    """
    
    return html


def create_email_text(deals):
    """Create a plain text version of the email."""
    
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    
    text = f"🔥 SLICKDEALS HOT DEALS - {date_str}\n"
    text += "=" * 50 + "\n\n"
    
    if not deals:
        text += "No hot deals found today. Check back tomorrow!\n"
    else:
        text += f"{len(deals)} hot deal{'s' if len(deals) != 1 else ''} found:\n\n"
        
        for i, deal in enumerate(deals, 1):
            text += f"{i}. {deal['title']}\n"
            if deal['price']:
                text += f"   Price: {deal['price']}\n"
            if deal['store']:
                text += f"   Store: {deal['store']}\n"
            if deal['link']:
                text += f"   Link: {deal['link']}\n"
            text += "\n"
    
    text += "-" * 50 + "\n"
    text += "Visit https://slickdeals.net for more deals.\n"
    
    return text


def send_email(deals):
    """Send the hot deals email."""
    
    if not SENDER_EMAIL or not SENDER_PASSWORD or not RECIPIENT_EMAIL:
        print("❌ Email credentials not configured. Set environment variables:")
        print("   SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"🔥 Slickdeals Hot Deals - {datetime.now().strftime('%b %d, %Y')}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    
    # Attach both plain text and HTML versions
    text_content = create_email_text(deals)
    html_content = create_email_html(deals)
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent successfully to {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Authentication failed. Check your email and app password.")
        return False
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


# ============================================
# MAIN EXECUTION
# ============================================

def main():
    print("🔍 Fetching hot deals from Slickdeals...")
    deals = get_hot_deals()
    
    print(f"📦 Found {len(deals)} hot deals")
    
    if deals:
        print("\nDeals found:")
        for deal in deals[:5]:  # Show first 5 in console
            print(f"  • {deal['title'][:60]}...")
        if len(deals) > 5:
            print(f"  ... and {len(deals) - 5} more")
    
    print("\n📧 Sending email...")
    send_email(deals)


if __name__ == "__main__":
    main()
