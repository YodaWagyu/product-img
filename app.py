import streamlit as st
import pandas as pd
import time
import random
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# ตั้งค่าหน้า Web App
st.set_page_config(page_title="Product Image Scraper", layout="wide")

st.title("🛒 Product Image Scraper")
st.markdown("""
เครื่องมือสำหรับดึงข้อมูลสินค้าจากเว็บ E-commerce โดยอัตโนมัติ
ระบบจะใช้ Browser จริงในการดึงข้อมูล เพื่อหลีกเลี่ยงการถูกบล็อก
""")

# --- ส่วนตั้งค่า (Configuration) ---
with st.expander("⚙️ ตั้งค่าการดึงข้อมูล (Settings)", expanded=True):
    col1, col2 = st.columns([2, 1])
    with col1:
        base_category_url = st.text_input(
            "🔗 URL หมวดหมู่สินค้า",
            value="",
            placeholder="วาง URL หมวดหมู่สินค้าที่ต้องการ...",
            help="ใส่ URL หมวดหมู่สินค้าที่ต้องการดึงข้อมูล"
        )
    
    with col2:
        max_pages = st.number_input(
            "จำนวนหน้าสูงสุด (Max Pages)", 
            min_value=1, 
            max_value=100, 
            value=5,
            help="ใส่เลขเยอะๆ เช่น 100 เพื่อดึงให้ครบทุกหน้าที่มี"
        )

def scrape_with_browser(base_url, max_pages):
    all_data = []
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    status_text.text("กำลังเปิด Browser...")
    
    with sync_playwright() as p:
        # เปิด Browser แบบ headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='th-TH'
        )
        page = context.new_page()
        
        for page_num in range(1, max_pages + 1):
            current_url = f"{base_url}?limit=100&page={page_num}"
            
            status_text.text(f"กำลังดึงข้อมูล... หน้าที่ {page_num}/{max_pages}")
            progress_bar.progress(page_num / max_pages)
            
            try:
                # เข้าหน้าเว็บ
                page.goto(current_url, wait_until='networkidle', timeout=30000)
                
                # รอให้ product cards โหลด
                page.wait_for_selector('[class*="productCard_container_"]', timeout=10000)
                
                # ดึง HTML
                content = page.content()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                product_cards = soup.find_all('div', class_=re.compile(r'productCard_container_'))
                
                if not product_cards:
                    status_text.success(f"สิ้นสุดข้อมูลที่หน้า {page_num-1}")
                    break
                
                for card in product_cards:
                    item = {}
                    
                    item['Scraped Date'] = current_timestamp
                    
                    name_el = card.find(class_=re.compile(r'productCard_title_'))
                    item['Product Name'] = name_el.get_text(strip=True) if name_el else "N/A"
                    
                    img_el = card.find('img')
                    if img_el:
                        img_url = img_el.get('src') or img_el.get('data-src')
                        item['Image URL'] = img_url
                        
                        if img_url:
                            barcode_match = re.search(r'(\d{8,14})', img_url)
                            item['Barcode'] = barcode_match.group(1) if barcode_match else ""
                        else:
                            item['Barcode'] = ""
                    else:
                        item['Image URL'] = ""
                        item['Barcode'] = ""
                    
                    price_container = card.find(class_=re.compile(r'productCard_price_'))
                    if price_container:
                        prices_text = price_container.get_text(strip=True)
                        numbers = re.findall(r'[\d,]+', prices_text)
                        
                        if len(numbers) >= 2:
                            item['Promotion Price'] = numbers[0]
                            item['Normal Price'] = numbers[1]
                        elif len(numbers) == 1:
                            item['Normal Price'] = numbers[0]
                            item['Promotion Price'] = numbers[0]
                        else:
                            item['Normal Price'] = "N/A"
                            item['Promotion Price'] = "N/A"
                    else:
                        item['Normal Price'] = "N/A"
                        item['Promotion Price'] = "N/A"
                    
                    all_data.append(item)
                
                # หน่วงเวลาสุ่ม
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                st.warning(f"หน้า {page_num}: {str(e)[:100]}")
                continue
        
        browser.close()
    
    return pd.DataFrame(all_data)

# ปุ่ม One-Click
if st.button("🚀 เริ่มดึงข้อมูล (Start Scraping)", type="primary"):
    if not base_category_url:
        st.error("กรุณาใส่ URL ก่อนเริ่มดึงข้อมูล")
    else:
        try:
            df = scrape_with_browser(base_category_url, max_pages)
            
            if not df.empty:
                st.success(f"เสร็จสิ้น! ดึงข้อมูลมาได้ทั้งหมด {len(df)} รายการ")
                
                st.dataframe(
                    df,
                    column_config={
                        "Image URL": st.column_config.ImageColumn("Image"),
                    },
                    use_container_width=True
                )
                
                csv = df.to_csv(index=False).encode('utf-8-sig')
                filename = f'products_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
                
                st.download_button(
                    label=f"💾 ดาวน์โหลดข้อมูล {len(df)} รายการ (CSV)",
                    data=csv,
                    file_name=filename,
                    mime='text/csv',
                )
            else:
                st.warning("ไม่พบข้อมูลสินค้า อาจมีการเปลี่ยนแปลงที่หน้าเว็บ")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {e}")
