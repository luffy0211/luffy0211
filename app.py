from flask import Flask, redirect, url_for, request, render_template
import mysql.connector
import logging
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# 配置数据库 URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/flask'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_mysql_connection():
    try:
        # 尝试建立与 MySQL 数据库的连接
        connection = mysql.connector.connect(
            host="localhost",
            user="root",
            password="123456",
            database="flask",
            port=3306
        )
        # 如果连接成功，记录成功信息
        logging.info("成功连接到 MySQL 数据库！")
        # 关闭连接
        connection.close()
        return True
    except mysql.connector.Error as err:
        # 如果连接失败，记录错误信息
        logging.error(f"连接 MySQL 数据库时出错: {err}")
        return False

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            return redirect(url_for('index'))
        else:
            return "用户名或密码错误，请重新输入。"
    return render_template('login.html')

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        if username and password:
            new_user = User(username=username, password=password, email=email)
            try:
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))
            except Exception as e:
                # 记录详细的错误信息
                logging.error(f"注册用户时出错: {e}")
                return "注册失败，可能用户名已存在。"
    return render_template('register.html')
@app.route('/index', methods=['POST', 'GET'])
def index():
    questions = request.form.get('questions')
    
    return render_template('index.html')

@app.route('/')
def root():
    return redirect(url_for('login'))

if __name__ == '__main__':
    test_mysql_connection()
    # 添加创建表的代码
    with app.app_context():
        db.create_all()
    app.run(debug=True)