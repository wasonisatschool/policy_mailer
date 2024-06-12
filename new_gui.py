import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import errorcode
import os
import schedule
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog

# 從環境變數中讀取資料庫連線資訊和爬取間隔
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'policy_tracker')
CRAWL_INTERVAL_DAYS = int(os.getenv('CRAWL_INTERVAL_DAYS', '3'))

# 安全的資料庫連線資訊
config = {
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': DB_HOST,
    'database': DB_NAME,
    'raise_on_warnings': True
}

# 檢查資料是否已存在的函式
def data_exists(title, date, url):
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        
        query = ("SELECT COUNT(*) FROM control_yuan_reports "
                 "WHERE title = %s AND date = %s AND url = %s")
        cursor.execute(query, (title, date, url))
        count = cursor.fetchone()[0]
        
        cursor.close()
        cnx.close()
        return count > 0
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False

# 插入資料的函式，防止SQL注入
def insert_data(title, date, url, content):
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()

        add_data = ("INSERT INTO control_yuan_reports "
                    "(title, date, url, content) "
                    "VALUES (%s, %s, %s, %s)")
        data = (title, date, url, content)

        cursor.execute(add_data, data)
        cnx.commit()

        cursor.close()
        cnx.close()
        print(f"資料已成功插入: {title}")
    
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("使用者名稱或密碼錯誤")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("資料庫不存在")
        else:
            print(err)

# 爬取給定的URL
def fetch_page_content(url):
    response = requests.get(url)
    response.encoding = 'utf-8'  # 設定編碼為UTF-8
    return response.text

# 提取內文與相關連結
def extract_content_and_links(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    # 提取內文
    content_div = soup.find('div', class_='area-essay page-caption-p')
    content_text = content_div.get_text(strip=True, separator='\n') if content_div else 'No content found'
    return content_text

# 定義函式來爬取指定頁數的新聞稿
def crawl_news(pages):
    base_url = 'https://www.cy.gov.tw/News.aspx?_CSN=129&n=792&page={}&PageSize=100&sms=8912&Create=1'

    for page in range(1, pages + 1):
        url = base_url.format(page)
        response = requests.get(url)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        news_list = soup.select('table tbody tr')

        for news in news_list:
            date = news.find('span').text.strip()
            title = news.find('a').text.strip()
            link = news.find('a')['href']
            news_url = 'https://www.cy.gov.tw/' + link
            html_content = fetch_page_content(news_url)
            content_text = extract_content_and_links(html_content)
            
            # 檢查資料是否已存在，若不存在則插入資料
            if not data_exists(title, date, news_url):
                insert_data(title, date, news_url, content_text)
            else:
                print(f"資料已存在: {title}")
                return  # 停止函式執行

# 定期爬取新聞稿的函式
def scheduled_crawl():
    crawl_news(5)

# 立即執行一次爬取
scheduled_crawl()

# 使用 schedule 設定定期任務
schedule.every(CRAWL_INTERVAL_DAYS).days.do(scheduled_crawl)

print(f"定期爬取任務已設定，每 {CRAWL_INTERVAL_DAYS} 天執行一次")

# 開始任務調度
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# GUI 設定
def setup_gui():
    def start_crawling():
        global DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, CRAWL_INTERVAL_DAYS
        DB_USER = user_entry.get()
        DB_PASSWORD = password_entry.get()
        DB_HOST = host_entry.get()
        DB_NAME = db_entry.get()
        CRAWL_INTERVAL_DAYS = int(interval_entry.get())
        
        # 更新配置
        config.update({
            'user': DB_USER,
            'password': DB_PASSWORD,
            'host': DB_HOST,
            'database': DB_NAME
        })
        
        messagebox.showinfo("Info", "設定成功，開始爬取新聞稿")
        scheduled_crawl()
        run_scheduler()

    root = tk.Tk()
    root.title("新聞爬取工具")
    root.geometry("400x300")

    # 應用程式圖標
    root.iconphoto(False, tk.PhotoImage(file='icon.png'))

    tk.Label(root, text="使用者名稱:").pack(pady=5)
    user_entry = tk.Entry(root)
    user_entry.pack(pady=5)

    tk.Label(root, text="密碼:").pack(pady=5)
    password_entry = tk.Entry(root, show="*")
    password_entry.pack(pady=5)

    tk.Label(root, text="主機:").pack(pady=5)
    host_entry = tk.Entry(root)
    host_entry.pack(pady=5)

    tk.Label(root, text="資料庫名稱:").pack(pady=5)
    db_entry = tk.Entry(root)
    db_entry.pack(pady=5)

    tk.Label(root, text="爬取間隔 (天):").pack(pady=5)
    interval_entry = tk.Entry(root)
    interval_entry.pack(pady=5)

    start_button = tk.Button(root, text="開始爬取", command=start_crawling)
    start_button.pack(pady=20)

    root.mainloop()

# 初始化 GUI
setup_gui()
