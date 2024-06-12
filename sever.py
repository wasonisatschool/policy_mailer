import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import errorcode
from flask import Flask, request, render_template, redirect, url_for, flash
import os
import schedule
import time
from threading import Thread

app = Flask(__name__)
app.secret_key = 'supersecretkey'

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

# 使用 schedule 設定定期任務
schedule.every(CRAWL_INTERVAL_DAYS).days.do(scheduled_crawl)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# 啟動排程執行緒
def start_scheduler_thread():
    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()

# Flask 路由
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        global DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, CRAWL_INTERVAL_DAYS
        DB_USER = request.form['user']
        DB_PASSWORD = request.form['password']
        DB_HOST = request.form['host']
        DB_NAME = request.form['database']
        CRAWL_INTERVAL_DAYS = int(request.form['interval'])

        # 更新配置
        config.update({
            'user': DB_USER,
            'password': DB_PASSWORD,
            'host': DB_HOST,
            'database': DB_NAME
        })

        flash('設定成功，開始爬取新聞稿', 'success')
        scheduled_crawl()
        return redirect(url_for('index'))
    return render_template('index.html')

if __name__ == '__main__':
    start_scheduler_thread()
    app.run(debug=True)
