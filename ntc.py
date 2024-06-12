from flask import Flask, render_template, request, flash, redirect, url_for
import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import errorcode
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 資料庫連線資訊
def get_db_config():
    return {
        'user': request.form['user'],
        'password': request.form.get('password', ''),  # 密碼可留空
        'host': request.form['host'],
        'database': request.form['database'],
        'raise_on_warnings': True
    }

# 檢查資料是否已存在的函式
def data_exists(title, date, url, config):
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()
        
        query = ("SELECT COUNT(*) FROM human_rights_statements "
                 "WHERE title = %s AND date = %s AND url = %s")
        cursor.execute(query, (title, date, url))
        count = cursor.fetchone()[0]
        
        cursor.close()
        cnx.close()
        return count > 0
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False

# 插入資料的函式
def insert_data(title, date, url, statement, config):
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor()

        add_data = ("INSERT INTO human_rights_statements "
                    "(title, date, url, statement) "
                    "VALUES (%s, %s, %s, %s)")
        data = (title, date, url, statement)

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
    content_div = soup.find('div', class_='area-essay')
    if content_div:
        content_text = content_div.get_text(strip=True, separator='\n')
    else:
        content_text = 'No content found'
    return content_text

# 檢查並格式化日期
def parse_date(date_str):
    try:
        # 將民國年轉換為西元年
        year, month, day = map(int, date_str.split('-'))
        year += 1911
        date = f"{year}-{month:02d}-{day:02d}"
        return date
    except ValueError:
        return '1970-01-01'  # 如果無法解析日期，使用默認值

# 定義函式來爬取指定頁數的新聞稿
def crawl_news(pages, config):
    base_url = 'https://nhrc.cy.gov.tw/News4.aspx?n=9772&sms=12362&_CSN=1&page={}&PageSize=20'

    for page in range(1, pages + 1):
        url = base_url.format(page)
        response = requests.get(url)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        news_list = soup.select('div.area-essay.message')

        for news in news_list:
            date_span = news.select_one('div.label > ul > li > span > i.mark')
            date = parse_date(date_span.text.strip()) if date_span else '1970-01-01'
            caption_div = news.find('div', class_='caption')
            title = caption_div.find('span').text.strip() if caption_div else '未知標題'
            link = news.find('a')['href']
            news_url = 'https://nhrc.cy.gov.tw/' + link
            html_content = fetch_page_content(news_url)
            content_text = extract_content_and_links(html_content)
            
            # 檢查資料是否已存在，若不存在則插入資料
            if not data_exists(title, date, news_url, config):
                insert_data(title, date, news_url, content_text, config)
            else:
                print(f"資料已存在: {title}")
                return  # 停止函式執行

    base_url = 'https://nhrc.cy.gov.tw/News4.aspx?n=9772&sms=12362&_CSN=1&page={}&PageSize=20'

    for page in range(1, pages + 1):
        url = base_url.format(page)
        response = requests.get(url)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        news_list = soup.select('div.area-essay.message')

        for news in news_list:
            date_span = news.find('li', class_='mark')
            date = parse_date(date_span.text.strip()) if date_span else '1970-01-01'
            caption_div = news.find('div', class_='caption')
            title = caption_div.find('span').text.strip() if caption_div else '未知標題'
            link = news.find('a')['href']
            news_url = 'https://nhrc.cy.gov.tw/' + link
            html_content = fetch_page_content(news_url)
            content_text = extract_content_and_links(html_content)
            
            # 檢查資料是否已存在，若不存在則插入資料
            if not data_exists(title, date, news_url, config):
                insert_data(title, date, news_url, content_text, config)
            else:
                print(f"資料已存在: {title}")
                return  # 停止函式執行

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        config = get_db_config()
        try:
            pages = int(request.form['pages'])
            crawl_news(pages, config)
            flash('爬取成功！', 'success')
        except Exception as e:
            flash(str(e), 'danger')
        return redirect(url_for('index'))
    return render_template('ntc_index.html')

if __name__ == '__main__':
    app.run(debug=True)
