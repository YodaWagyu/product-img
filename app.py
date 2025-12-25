import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
from datetime import datetime

# ตั้งค่าหน้า Web App
st.set_page_config(page_title="BigC Beauty Scraper", layout="wide")

st.title("💄 BigC Beauty & Personal Care Scraper")
st.markdown("""
แอปพลิเคชันสำหรับดึงข้อมูลสินค้าหมวด **Beauty & Personal Care** ทั้งหมดโดยอัตโนมัติ
ระบบจะวนลูปดึงข้อมูลทีละหน้าจนครบ หรือจนกว่าจะถึงขีดจำกัดที่กำหนด
""")

# --- ส่วนตั้งค่า (Configuration) ---
with st.expander("⚙️ ตั้งค่าการดึงข้อมูล (Settings)", expanded=True):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info("เป้าหมาย: https://www.bigc.co.th/category/beauty-personal-care")
        base_category_url = "https://www.bigc.co.th/category/beauty-personal-care"
    
    with col2:
        # ให้ User เลือกได้ว่าจะดึงกี่หน้า (เผื่อแค่อยากเทส)
        max_pages = st.number_input(
            "จำนวนหน้าสูงสุดที่ต้องการดึง (Max Pages)", 
            min_value=1, 
            max_value=100, 
            value=5, # ค่าเริ่มต้นเซ็ตไว้ 5 หน้าเพื่อทดสอบเร็วๆ ถ้าจะเอาหมดให้ใส่เยอะๆ
            help="ใส่เลขเยอะๆ เช่น 100 เพื่อดึงให้ครบทุกหน้าที่มี"
        )

# ฟังก์ชันสำหรับดึงข้อมูล (รองรับ Loop หลายหน้า)
def scrape_all_pages(base_url, max_pages):
    all_data = []
    
    # Placeholder สำหรับแสดงสถานะการทำงานแบบ Real-time
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # จับเวลาตอนเริ่มดึงข้อมูล
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8'
    }

    # Loop ตามจำนวนหน้าที่กำหนด
    for page in range(1, max_pages + 1):
        # สร้าง URL สำหรับแต่ละหน้า (query string: limit=100&page=X)
        current_url = f"{base_url}?limit=100&page={page}"
        
        status_text.text(f"กำลังดึงข้อมูล... หน้าที่ {page}/{max_pages} ({current_url})")
        progress_bar.progress(page / max_pages)

        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                st.warning(f"หน้า {page} โหลดไม่สำเร็จ (Status: {response.status_code}) ข้ามไปหน้าถัดไป...")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # ค้นหา Container ของสินค้า
            product_cards = soup.find_all('div', class_=re.compile(r'productCard_container_'))
            
            # ถ้าหน้านี้ไม่มีสินค้าเลย แสดงว่าหมดแล้ว -> หยุด Loop ทันที
            if not product_cards:
                status_text.success(f"สิ้นสุดข้อมูลที่หน้า {page-1}")
                break

            # วนลูปสินค้าในหน้านั้นๆ
            for card in product_cards:
                item = {}
                
                # 0. Scraped Date (เพิ่มวันที่ดึงข้อมูล)
                item['Scraped Date'] = current_timestamp

                # 1. Product Name
                name_el = card.find(class_=re.compile(r'productCard_title_'))
                item['Product Name'] = name_el.get_text(strip=True) if name_el else "N/A"
                
                # 2. Images & Barcode Extraction
                img_el = card.find('img')
                if img_el:
                    img_url = img_el.get('src') or img_el.get('data-src')
                    item['Image URL'] = img_url
                    
                    if img_url:
                        # หาตัวเลข 8-14 หลักใน URL
                        barcode_match = re.search(r'(\d{8,14})', img_url)
                        item['Barcode'] = barcode_match.group(1) if barcode_match else ""
                    else:
                        item['Barcode'] = ""
                else:
                    item['Image URL'] = ""
                    item['Barcode'] = ""

                # 3. Prices
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
            
            # หน่วงเวลาสุ่ม 1-2 วินาที ก่อนไปหน้าถัดไป (กันโดนบล็อก)
            time.sleep(random.uniform(0.5, 1.5))

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดที่หน้า {page}: {e}")
            continue
            
    return pd.DataFrame(all_data)

# ปุ่ม One-Click
if st.button("🚀 เริ่มดึงข้อมูลทั้งหมด (Start Scraping)", type="primary"):
    
    df = scrape_all_pages(base_category_url, max_pages)
    
    if not df.empty:
        st.success(f"เสร็จสิ้น! ดึงข้อมูลมาได้ทั้งหมด {len(df)} รายการ")
        
        # แสดงข้อมูล
        st.dataframe(
            df,
            column_config={
                "Image URL": st.column_config.ImageColumn("Image"),
            },
            use_container_width=True
        )
        
        # ปุ่มดาวน์โหลด
        csv = df.to_csv(index=False).encode('utf-8-sig')
        # สร้างชื่อไฟล์ให้มีวันที่แปะท้ายด้วย เพื่อให้แยกไฟล์ง่ายๆ
        filename = f'bigc_beauty_products_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
        
        st.download_button(
            label=f"💾 ดาวน์โหลดข้อมูล {len(df)} รายการ (CSV)",
            data=csv,
            file_name=filename,
            mime='text/csv',
        )
    else:
        st.warning("ไม่พบข้อมูลสินค้าเลย อาจมีการเปลี่ยนแปลงที่หน้าเว็บ")
