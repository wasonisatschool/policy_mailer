import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import errorcode
import sys
import schedule
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QFormLayout,
                             QLineEdit, QPushButton, QLabel, QTextEdit, QSpinBox, QHBoxLayout)
from PyQt5.QtCore import QTimer, Qt

class CrawlerApp(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle('News Crawler')
        self.setGeometry(100, 100, 600, 400)
        
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        self.db_user = QLineEdit('root')
        self.db_password = QLineEdit('')
        self.db_password.setEchoMode(QLineEdit.Password)
        self.db_host = QLineEdit('localhost')
        self.db_name = QLineEdit('policy_tracker')
        self.crawl_interval_days = QSpinBox()
        self.crawl_interval_days.setValue(3)
        
        form_layout.addRow('DB User:', self.db_user)
        form_layout.addRow('DB Password:', self.db_password)
        form_layout.addRow('DB Host:', self.db_host)
        form_layout.addRow('DB Name:', self.db_name)
        form_layout.addRow('Crawl Interval (Days):', self.crawl_interval_days)

        layout.addLayout(form_layout)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet("background-color: #f0f0f0; color: #333; font: 12pt 'Courier New'; padding: 10px; border: 1px solid #ccc;")
        
        self.start_button = QPushButton('Start Crawler')
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; font: 14pt 'Arial'; padding: 10px 20px; border-radius: 5px;")
        self.start_button.clicked.connect(self.start_crawler)
        
        layout.addWidget(self.output)
        layout.addWidget(self.start_button)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
            }
            QLabel {
                font: 12pt 'Arial';
            }
            QLineEdit {
                font: 12pt 'Arial';
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QSpinBox {
                font: 12pt 'Arial';
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        """)

    def start_crawler(self):
        self.config = {
            'user': self.db_user.text(),
            'password': self.db_password.text(),
            'host': self.db_host.text(),
            'database': self.db_name.text(),
            'raise_on_warnings': True
        }
        
        self.crawl_interval_days_value = self.crawl_interval_days.value()
        
        self.log(f"Configuration set. DB Host: {self.config['host']}, DB User: {self.config['user']}, DB Name: {self.config['database']}, Crawl Interval: {self.crawl_interval_days_value} days")
        
        self.scheduled_crawl()
        
        schedule.every(self.crawl_interval_days_value).days.do(self.scheduled_crawl)
        
        self.log(f"Scheduled crawl every {self.crawl_interval_days_value} days")
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_pending)
        self.timer.start(1000)
        
    def run_pending(self):
        schedule.run_pending()
    
    def log(self, message):
        self.output.append(message)

    def data_exists(self, title, date, url):
        try:
            cnx = mysql.connector.connect(**self.config)
            cursor = cnx.cursor()

            query = ("SELECT COUNT(*) FROM control_yuan_reports "
                     "WHERE title = %s AND date = %s AND url = %s")
            cursor.execute(query, (title, date, url))
            count = cursor.fetchone()[0]

            cursor.close()
            cnx.close()
            return count > 0

        except mysql.connector.Error as err:
            self.log(f"Error: {err}")
            return False

    def insert_data(self, title, date, url, content):
        try:
            cnx = mysql.connector.connect(**self.config)
            cursor = cnx.cursor()

            add_data = ("INSERT INTO control_yuan_reports "
                        "(title, date, url, content) "
                        "VALUES (%s, %s, %s, %s)")
            data = (title, date, url, content)

            cursor.execute(add_data, data)
            cnx.commit()

            cursor.close()
            cnx.close()
            self.log(f"Data inserted: {title}")

        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                self.log("Access denied: Invalid username or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                self.log("Database does not exist")
            else:
                self.log(f"Error: {err}")

    def fetch_page_content(self, url):
        response = requests.get(url)
        response.encoding = 'utf-8'  # 設定編碼為UTF-8
        return response.text

    def extract_content_and_links(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        # 提取內文
        content_div = soup.find('div', class_='area-essay page-caption-p')
        content_text = content_div.get_text(strip=True, separator='\n') if content_div else 'No content found'
        return content_text

    def crawl_news(self, pages):
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
                html_content = self.fetch_page_content(news_url)
                content_text = self.extract_content_and_links(html_content)

                # 檢查資料是否已存在，若不存在則插入資料
                if not self.data_exists(title, date, news_url):
                    self.insert_data(title, date, news_url, content_text)
                else:
                    self.log(f"Data already exists: {title}")
                    return  # 停止函式執行

    def scheduled_crawl(self):
        self.crawl_news(5)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CrawlerApp()
    ex.show()
    sys.exit(app.exec_())
