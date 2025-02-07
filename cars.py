from flask import Flask, request, redirect, jsonify, render_template, flash, session, url_for
import mysql.connector
import os
from werkzeug.utils import secure_filename
import logging
import requests
from flask_mail import Mail, Message
from functools import wraps
import random
import string
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import stripe

app = Flask(__name__)
app.secret_key = "your secret key"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_IMAGE_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'xxxxxxx'  # Replace with your email
app.config['MAIL_PASSWORD'] = 'xxxxxxxxx'  # Replace with your App Password
mail = Mail(app)

# Serializer for generating and validating tokens
serializer = URLSafeTimedSerializer(app.secret_key)

# Stripe configuration
stripe_keys = {
    'secret_key': 'sk_test_51Qp8AoAlk9jUnG6qSeP6fwyWAc8CPmdCOeXBPjRxM1yZDedP0sSdfsZOdCbq0wanzXlPHGcCkX9L4qC668cSV1OS00A0i904sZ',
    'publishable_key': 'pk_test_51Qp8AoAlk9jUnG6qaJCaFuTKyH5x4R5MQVjbEK158SMeBwmivXrqK7GizkDePBKCN3g5kmbqwiu7PrL4M7stOlfV00hcBgoqvi'
}
stripe.api_key = stripe_keys['secret_key']

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_IMAGE_EXTENSIONS']

try:
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='xxxxxxx',
        database='xxxxxx'
    )
    cursor = conn.cursor(dictionary=True)
except mysql.connector.Error as e:
    logging.error("Error connecting to MySQL database: %s", e)

# Helper function to check if user is logged in:
def is_logged_in():
    return 'user_id' in session

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form.get('email')
    cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
    user = cursor.fetchone()
    if user:
        otp = generate_otp()
        session['otp'] = otp
        session['otp_email'] = email

        msg = Message('Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP code is {otp}. It is valid for 10 minutes.'
        try:
            mail.send(msg)
            flash('OTP has been sent to your email.', 'success')
            return redirect(url_for('verify_otp'))
        except Exception as e:
            logging.error("Error sending email: %s", e)
            flash('An error occurred while sending the OTP. Please try again later.', 'danger')
            return redirect(url_for('login'))
    else:
        flash('Email not found!', 'danger')
        return redirect(url_for('login'))

# @app.route('/verify_otp', methods=['GET', 'POST'])
# def verify_otp():
#     if request.method == 'POST':
#         otp = request.form.get('otp')
#         if otp == session.get('otp'):
#             email = session.get('otp_email')
#             username = session.get('username')
#             cursor.execute('SELECT * FROM users WHERE email = %s AND username = %s', (email, username))
#             user = cursor.fetchone()
#             cursor.fetchall()  # Ensure all results are fetched
#             if user:
#                 session['loggedin'] = True
#                 session['user_id'] = user['user_id']
#                 session['username'] = user['username']
#                 session['role'] = user.get('role', 'user')
#                 session.pop('otp', None)
#                 session.pop('otp_email', None)
#                 return redirect(url_for('home'))
#             else:
#                 flash('User not found!', 'danger')
#                 return redirect(url_for('login'))
#         else:
#             flash('Invalid OTP!', 'danger')
#             return redirect(url_for('verify_otp'))
#     return render_template('verify_otp.html')

@app.route('/')
@app.route('/home')
def home():
    try:
        # Fetch top picked cars
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.price_per_day, Cars.image_url, Companies.company_name
            FROM Cars
            JOIN Companies ON Cars.company_id = Companies.company_id
            ORDER BY Cars.price_per_day DESC
            LIMIT 5
        ''')
        top_picked_cars = cursor.fetchall()
        for car in top_picked_cars:
            car['image_url'] = url_for('static', filename='uploads/' + (car['image_url'] or ''))

        # Fetch latest added cars
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.price_per_day, Cars.image_url, Companies.company_name
            FROM Cars
            JOIN Companies ON Cars.company_id = Companies.company_id
            ORDER BY Cars.car_id DESC
            LIMIT 5
        ''')
        latest_added_cars = cursor.fetchall()
        for car in latest_added_cars:
            car['image_url'] = url_for('static', filename='uploads/' + (car['image_url'] or ''))

        return render_template('index.html', top_picked_cars=top_picked_cars, latest_added_cars=latest_added_cars)
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        flash('Database error occurred. Please try again later!', 'danger')
        return redirect(url_for('home'))
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        flash('An unexpected error occurred. Please try again later!', 'danger')
        return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirmpassword')
            address1 = request.form.get('addressLine1')
            address2 = request.form.get('addressLine2')
            state = request.form.get('state')
            city = request.form.get('city')
            country = request.form.get('country')
            dob = request.form.get('dob')
            phone = request.form.get('phonenumber')
            role = request.form.get('role')
            gender = request.form.get('gender')
            # Image file handling
            image_filename = None
            if 'picture' in request.files and request.files['picture'].filename:
                image_file = request.files['picture']
                if allowed_image_file(image_file.filename):
                    image_filename = secure_filename(image_file.filename)
                    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                else:
                    return jsonify({'message': 'Invalid image file format'}), 400
            # Password matching check
            if password != confirm_password:
                return jsonify({'message': 'Passwords do not match'}), 400
            # Check if user exists
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            account = cursor.fetchone()
            if account:
                return jsonify({'message': 'Account already exists'}), 400
            # Insert user into users table
            cursor.execute(
                'INSERT INTO users (username, password, role, email) VALUES (%s, %s, %s, %s)',
                (username, password, role, email)  # Store plain password
            )
            user_id = cursor.lastrowid  # Get the newly created user ID
            # Insert user profile details
            cursor.execute(
                '''INSERT INTO user_profile 
                (user_id, phone_number, profile_picture, email, address_line1, address_line2, birthday, gender, state, city, country) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                (user_id, phone, image_filename, email, address1, address2, dob, gender, state, city, country)
            )        
            conn.commit()  # Save changes
            return jsonify({'message': 'You have successfully registered!'}), 200
        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            return jsonify({'message': 'Database error occurred. Please try again later!'}), 500
        except ValueError as e:
            logging.error("Value error: %s", e)
            return jsonify({'message': str(e)}), 400
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify({'message': 'An unexpected error occurred. Please try again later!'}), 500
    return render_template('register.html')

@app.route('/about')
def about():
     return render_template('about.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        cursor.execute('SELECT * FROM users WHERE username = %s AND email = %s', (username, email))
        account = cursor.fetchone()
        
        if account:
            otp = generate_otp()
            session['otp'] = otp
            session['otp_email'] = email
            session['username'] = username
            session['user_id'] = account['user_id']  # Ensure user_id is set in session
            session['loggedin'] = True  # Ensure this line is present

            msg = Message('Your OTP Code', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Your OTP code is {otp}. It is valid for 10 minutes.'
            try:
                mail.send(msg)
                flash('OTP has been sent to your email.', 'success')
                return redirect(url_for('verify_otp'))
            except Exception as e:
                logging.error("Error sending email: %s", e)
                flash('An error occurred while sending the OTP. Please try again later.', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Incorrect username or email!', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        otp = request.form.get('otp')
        if otp == session.get('otp'):
            email = session.get('otp_email')
            username = session.get('username')
            cursor.execute('SELECT * FROM users WHERE email = %s AND username = %s', (email, username))
            user = cursor.fetchone()
            cursor.fetchall()  # Ensure all results are fetched
            if user:
                session['username'] = user['username']
                session['role'] = user.get('role', 'user')
                session['user_id'] = user['user_id']
                session.pop('otp', None)
                session.pop('otp_email', None)
                return redirect(url_for('home'))
            else:
                flash('User not found!', 'danger')
                return redirect(url_for('login'))
        else:
            flash('Invalid OTP!', 'danger')
            return redirect(url_for('verify_otp'))
    return render_template('verify_otp.html')

@app.route('/add_car', methods=['GET', 'POST'])
@app.route('/edit_car/<int:car_id>', methods=['GET', 'POST'])
def add_or_edit_car(car_id=None):
    if 'loggedin' in session:
        owner_id = session.get('user_id')
        if not owner_id:
            logging.error("User ID not found in session.")
            flash('User ID not found. Please log in again.', 'danger')
            return redirect(url_for('login'))

        if request.method == 'POST':
            try:
                car_name = request.form.get('car_name')
                car_number = request.form.get('car_number')
                type_name = request.form.get('car_type')
                if (type_name == "Other"):
                    type_name = request.form.get('car_type_name')
                company_name = request.form.get('company_name')
                if (company_name == "Other"):
                    company_name = request.form.get('company_name_input')
                stock = request.form.get('stock')
                price_per_day = request.form.get('price')
                from_location = request.form.get('from_location')
                to_location = request.form.get('to_location')

                # Validate form data
                if not car_name or not car_number or not type_name or not company_name or not stock or not price_per_day or not from_location or not to_location:
                    flash("All fields are required", "danger")
                    return redirect(url_for('add_or_edit_car', car_id=car_id))

                # Check if company exists, if not, add it
                cursor.execute('SELECT company_id FROM Companies WHERE company_name = %s', (company_name,))
                company = cursor.fetchone()
                if not company:
                    cursor.execute('INSERT INTO Companies (company_name, company_description, user_id) VALUES (%s, %s, %s)', (company_name, company_name, owner_id))
                    company_id = cursor.lastrowid
                else:
                    company_id = company['company_id']

                # Check if car type exists, if not, add it
                cursor.execute('SELECT type_id FROM CarTypes WHERE type_name = %s', (type_name,))
                car_type = cursor.fetchone()
                if not car_type:
                    cursor.execute('INSERT INTO CarTypes (type_name, type_description, user_id) VALUES (%s, %s, %s)', (type_name, type_name, owner_id))
                    type_id = cursor.lastrowid
                else:
                    type_id = car_type['type_id']

                # Image file handling
                image_filename = None
                if 'car_image' in request.files and request.files['car_image'].filename:
                    image_file = request.files['car_image']
                    if allowed_image_file(image_file.filename):
                        image_filename = secure_filename(image_file.filename)
                        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                    else:
                        flash("Invalid image file format", "danger")
                        return redirect(url_for('add_or_edit_car', car_id=car_id))
                else:
                    # If no new image is uploaded, keep the existing image
                    if car_id:
                        cursor.execute('SELECT image_url FROM Cars WHERE car_id = %s', (car_id,))
                        existing_car = cursor.fetchone()
                        if existing_car:
                            image_filename = existing_car['image_url']

                if car_id:
                    # Update car data in Cars table
                    cursor.execute(
                        '''UPDATE Cars SET car_name=%s, car_number=%s, type_id=%s, company_id=%s, stock=%s, price_per_day=%s, from_location=%s, to_location=%s, image_url=%s
                        WHERE car_id=%s AND owner_id=%s''',
                        (car_name, car_number, type_id, company_id, stock, price_per_day, from_location, to_location, image_filename, car_id, owner_id)
                    )
                else:
                    # Insert car data into Cars table
                    cursor.execute(
                        '''INSERT INTO Cars 
                        (owner_id, car_name, car_number, type_id, company_id, stock, price_per_day, from_location, to_location, image_url)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                        (owner_id, car_name, car_number, type_id, company_id, stock, price_per_day, from_location, to_location, image_filename)
                    )
                conn.commit()  # Save changes

                return redirect(url_for('car_reports'))

            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
                return redirect(url_for('add_or_edit_car', car_id=car_id))

            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')
                return redirect(url_for('add_or_edit_car', car_id=car_id))

        car = None
        # Fetch car types and companies from the database
        cursor.execute('SELECT type_name FROM CarTypes')
        car_types = cursor.fetchall()
        cursor.execute('SELECT company_name FROM Companies')
        companies = cursor.fetchall()

        if car_id:
            cursor.execute('''
                SELECT Cars.*, CarTypes.type_name, Companies.company_name
                FROM Cars
                JOIN CarTypes ON Cars.type_id = CarTypes.type_id
                JOIN Companies ON Cars.company_id = Companies.company_id
                WHERE Cars.car_id = %s AND Cars.owner_id = %s
            ''', (car_id, session['user_id']))
            car = cursor.fetchone()

        return render_template('add_car.html', car=car, car_types=car_types, companies=companies)
    return redirect(url_for('login'))

@app.route('/add_car_type', methods=['GET', 'POST'])
@app.route('/edit_car_type/<int:type_id>', methods=['GET', 'POST'])
def add_or_edit_car_type(type_id=None):
    if 'loggedin' in session and session.get('role') == 'admin':
        user_id = session.get('user_id')
        # if not user_id:
        #     logging.error("User ID not found in session.")
        #     flash('User ID not found. Please log in again.', 'danger')
        #     return redirect(url_for('login'))

        if request.method == 'POST':
            try:
                car_type_name = request.form.get('carTypeName')
                car_type_desc = request.form.get('carTypeDesc')
                user_id = session['user_id']
                print(user_id)
                if type_id:
                    cursor.execute('''
                        UPDATE CarTypes SET type_name=%s, type_description=%s WHERE type_id=%s
                    ''', (car_type_name, car_type_desc, type_id))
                else:
                    cursor.execute('''
                        INSERT INTO CarTypes (type_name, type_description, user_id) VALUES (%s, %s, %s)
                    ''', (car_type_name, car_type_desc, user_id))
                conn.commit()

                flash('Car type saved successfully!', 'success')
                return redirect(url_for('car_type_report'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        car_type = None
        if type_id:
            cursor.execute('SELECT * FROM CarTypes WHERE type_id = %s', (type_id,))
            car_type = cursor.fetchone()

        return render_template('add_car_type.html', car_type=car_type)
    return redirect(url_for('login'))

@app.route('/add_company', methods=['GET', 'POST'])
@app.route('/edit_company/<int:company_id>', methods=['GET', 'POST'])
def add_or_edit_company(company_id=None):
    if 'loggedin' in session and session.get('role') == 'admin':
        user_id = session.get('user_id')
        # if not user_id:
        #     logging.error("User ID not found in session.")
        #     flash('User ID not found. Please log in again.', 'danger')
        #     return redirect(url_for('login'))

        if request.method == 'POST':
            try:
                company_name = request.form.get('company_name')
                company_description = request.form.get('company_description')
                user_id = session['user_id']

                if company_id:
                    cursor.execute('''
                        UPDATE Companies SET company_name=%s, company_description=%s WHERE company_id=%s
                    ''', (company_name, company_description, company_id))
                else:
                    cursor.execute('''
                        INSERT INTO Companies (company_name, company_description, user_id) VALUES (%s, %s, %s)
                    ''', (company_name, company_description, user_id))
                conn.commit()

                flash('Company saved successfully!', 'success')
                return redirect(url_for('company_report'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        company = None
        if company_id:
            cursor.execute('SELECT * FROM Companies WHERE company_id = %s', (company_id,))
            company = cursor.fetchone()

        return render_template('add_company.html', company=company)
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()  # Clear the entire session
    return redirect(url_for('home'))  # Redirect to home page

@app.route('/check_login', methods=['GET'])
def check_login():
    if 'loggedin' in session:
        return jsonify(logged_in=True)
    else:
        return jsonify(logged_in(False))
    
def fetch_distinct_locations():
    try:
        cursor.execute('SELECT DISTINCT from_location FROM Cars')
        from_locations = cursor.fetchall()
        logging.info(f"Fetched from_locations: {from_locations}")
        cursor.execute('SELECT DISTINCT to_location FROM Cars')
        to_locations = cursor.fetchall()
        logging.info(f"Fetched to_locations: {to_locations}")
        return from_locations, to_locations
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        flash('Database error occurred. Please try again later!', 'danger')
        return [], []

@app.route('/book_car', methods=['GET', 'POST'])
def book_car():
    if 'loggedin' in session:
        try:
            cursor.execute('SELECT DISTINCT from_location FROM Cars')
            from_locations = cursor.fetchall()
            cursor.execute('SELECT DISTINCT to_location FROM Cars')
            to_locations = cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return render_template('book_car.html', from_locations=[], to_locations=[])

        available_cars = []
        if request.method == 'POST':
            car_id = request.form.get('car_id')
            pickup_date = request.form.get('pickup_date')
            dropoff_date = request.form.get('dropoff_date')
            from_location = request.form.get('from_location')
            to_location = request.form.get('to_location')

            try:
                query = '''
                    SELECT Cars.car_id, Cars.car_name, Cars.price_per_day, Cars.image_url, Companies.company_name
                    FROM Cars
                    JOIN Companies ON Cars.company_id = Companies.company_id
                    WHERE Cars.from_location = %s AND Cars.to_location = %s
                    AND Cars.car_id NOT IN (
                        SELECT car_id FROM Bookings
                        WHERE (pickup_date BETWEEN %s AND %s)
                        OR (dropoff_date BETWEEN %s AND %s)
                        OR (%s BETWEEN pickup_date AND dropoff_date)
                        OR (%s BETWEEN pickup_date AND dropoff_date)
                    )
                '''
                cursor.execute(query, (from_location, to_location, pickup_date, dropoff_date, pickup_date, dropoff_date, pickup_date, dropoff_date))
                available_cars = cursor.fetchall()
            except mysql.connector.Error as e:
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
                available_cars = []

            if not available_cars:
                flash('No cars available for the selected dates and locations.', 'danger')

        return render_template('book_car.html', from_locations=from_locations, to_locations=to_locations, available_cars=available_cars)
    return redirect(url_for('login'))


@app.route('/book_car_confirm/<int:car_id>', methods=['GET', 'POST'])
def book_car_confirm(car_id):
    if 'loggedin' in session:
        try:
            user_id = session['user_id']
            if request.method == 'POST':
                pickup_date = request.form.get('pickup_date')
                dropoff_date = request.form.get('dropoff_date')
            else:
                pickup_date = request.args.get('pickup_date')
                dropoff_date = request.args.get('dropoff_date')

            # Fetch car details
            cursor.execute('''
                SELECT Cars.car_id, Cars.car_name, Cars.stock, Cars.price_per_day, Cars.image_url, 
                       CarTypes.type_name, Companies.company_name, Users.username, user_profile.phone_number,
                       Cars.from_location, Cars.to_location
                FROM Cars
                JOIN CarTypes ON Cars.type_id = CarTypes.type_id
                JOIN Companies ON Cars.company_id = Companies.company_id
                JOIN Users ON Cars.owner_id = Users.user_id
                JOIN user_profile ON Users.user_id = user_profile.user_id
                WHERE Cars.car_id = %s
            ''', (car_id,))
            car = cursor.fetchone()

            if not car:
                flash('Car not found!', 'danger')
                return redirect(url_for('book_car'))

            # Render the booking confirmation page with car details
            return render_template('booking.html', car=car, pickup_date=pickup_date, dropoff_date=dropoff_date)

        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

    return redirect(url_for('login'))

@app.route('/add_booking_details/<int:car_id>', methods=['POST'])
def add_booking_details(car_id):
    if 'loggedin' in session:
        try:
            user_id = session['user_id']
            cursor.execute('SELECT username FROM users WHERE user_id = %s', (user_id,))
            user = cursor.fetchone()
            customer_name = user['username']  # Fetch the username from the users table
            email = request.form.get('email')
            pickup_date = request.form.get('pickupDate')
            dropoff_date = request.form.get('dropoffDate')
            pickup_address = request.form.get('pickupAddress')
            dropoff_address = request.form.get('dropoffAddress')

            # Validate date fields
            if not pickup_date or not dropoff_date:
                flash('Please enter valid pickup and dropoff dates.', 'danger')
                return redirect(url_for('book_car_confirm', car_id=car_id))

            # Insert booking details into the database
            cursor.execute(
                '''INSERT INTO Bookings (user_id, car_id, customer_name, email, pickup_date, dropoff_date, pickup_address, dropoff_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (user_id, car_id, customer_name, email, pickup_date, dropoff_date, pickup_address, dropoff_address)
            )
            conn.commit()

            flash('Car booked successfully!', 'success')
            return redirect(url_for('booking_report'))

        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

    return redirect(url_for('login'))

@app.route('/user_dashboard')
def user_dashboard():
    if 'loggedin' in session:
        user_id = session['user_id']
        # Fetch cars added by the user
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.stock, Cars.price_per_day, Cars.image_url, 
                   CarTypes.type_name, Companies.company_name, Users.username,
                   Cars.from_location, Cars.to_location
            FROM Cars
            JOIN CarTypes ON Cars.type_id = CarTypes.type_id
            JOIN Companies ON Cars.company_id = Companies.company_id
            JOIN Users ON Cars.owner_id = Users.user_id
            WHERE Cars.owner_id = %s
        ''', (user_id,))
        user_cars = cursor.fetchall()

        # Fetch bookings made by the user
        cursor.execute('''
            SELECT Bookings.booking_id, Bookings.customer_name, Bookings.email, 
                   CONCAT(Bookings.pickup_date, ' to ', Bookings.dropoff_date) AS booking_period,
                   CONCAT(Bookings.pickup_address, ' to ', Bookings.dropoff_address) AS booking_location,
                   Cars.car_name, Cars.price_per_day, Cars.image_url AS car_image_url,
                   CarTypes.type_name AS car_type, Companies.company_name,
                   Users.username AS owner_username, user_profile.phone_number AS owner_phone_number
            FROM Bookings
            JOIN Cars ON Bookings.car_id = Cars.car_id
            JOIN CarTypes ON Cars.type_id = CarTypes.type_id
            JOIN Companies ON Cars.company_id = Companies.company_id
            JOIN Users ON Cars.owner_id = Users.user_id
            JOIN user_profile ON Users.user_id = user_profile.user_id
            WHERE Bookings.user_id = %s
        ''', (user_id,))
        user_bookings = cursor.fetchall()

        return render_template('user_dashboard.html', user_cars=user_cars, user_bookings=user_bookings)
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')  

@app.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if request.method == 'POST':
        email = request.form.get('email')
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        if user:
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Please click the link to reset your password: {reset_url}'
            try:
                mail.send(msg)
                flash('A password reset link has been sent to your email.', 'success')
            except Exception as e:
                logging.error("Error sending email: %s", e)
                flash('An error occurred while sending the email. Please try again later.', 'danger')
        else:
            flash('Email not found!', 'danger')
        return redirect(url_for('login'))
    return render_template('forget_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forget_password'))

    if request.method == 'POST':
        new_password = request.form.get('newPassword')
        confirm_password = request.form.get('confirmPassword')
        if new_password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('reset_password', token=token))
        cursor.execute('SELECT user_id FROM user_profile WHERE email = %s', (email,))
        user_profile = cursor.fetchone()
        if user_profile:
            user_id = user_profile['user_id']
            cursor.execute('UPDATE users SET password = %s WHERE user_id = %s', (new_password, user_id))
            conn.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)

@app.route('/car_reports')
def car_reports():
    if 'loggedin' in session:
        try:
            page = request.args.get('page', 1, type=int)
            per_page = 5
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT Cars.car_id, Cars.car_name, Cars.car_number, Cars.stock, Cars.price_per_day, Cars.image_url, 
                       CarTypes.type_name, Companies.company_name, Users.username,
                       Cars.from_location, Cars.to_location
                FROM Cars
                JOIN CarTypes ON Cars.type_id = CarTypes.type_id
                JOIN Companies ON Cars.company_id = Companies.company_id
                JOIN Users ON Cars.owner_id = Users.user_id
                WHERE Cars.owner_id = %s
                LIMIT %s OFFSET %s
            ''', (session['user_id'], per_page, offset))
            cars = cursor.fetchall()
            cursor.execute('SELECT COUNT(*) FROM Cars WHERE owner_id = %s', (session['user_id'],))
            total = cursor.fetchone()['COUNT(*)']
            total_pages = (total + per_page - 1) // per_page
            return render_template('car_reports.html', cars=cars, page=page, total_pages=total_pages)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('admin_dashboard'))
    else:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # Create the email content
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=['19512varsha@gmail.com'])
        msg.body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"

        try:
            mail.send(msg)
            flash('Your message has been sent successfully!', 'success')
        except Exception as e:
            logging.error("Error sending email: %s", e)
            flash('An error occurred while sending your message. Please try again later.', 'danger')

        return redirect(url_for('contact'))

    return render_template('contact.html')



@app.route('/change_pswd', methods=['GET', 'POST'])
def change_pswd():
    if 'loggedin' in session:
        if request.method == 'POST':
            current_password = request.form.get('currentPassword')
            new_password = request.form.get('newPassword')
            confirm_password = request.form.get('confirmPassword')

            if new_password != confirm_password:
                flash('New passwords do not match!', 'danger')
                return redirect(url_for('change_pswd'))

            cursor.execute('SELECT password FROM users WHERE user_id = %s', (session['user_id'],))
            user = cursor.fetchone()

            if user and user['password'] == current_password:
                cursor.execute('UPDATE users SET password = %s WHERE user_id = %s', (new_password, session['user_id']))
                conn.commit()
                flash('Password changed successfully!', 'success')
                return redirect(url_for('change_pswd'))
            else:
                flash('Current password is incorrect!', 'danger')
                return redirect(url_for('change_pswd'))

        return render_template('change_pswd.html')
    return redirect(url_for('login'))


@app.route('/cars', methods=['GET'])
def cars():
    price_min = request.args.get('price_min')
    price_max = request.args.get('price_max')
    company = request.args.get('company')
    car_type = request.args.get('car_type')
    location = request.args.get('location')
    sort_price = request.args.get('sort_price')

    query = '''
        SELECT Cars.car_id, Cars.car_name, Cars.stock, Cars.price_per_day, Cars.image_url, 
               CarTypes.type_name, Companies.company_name, Cars.from_location, Cars.to_location
        FROM Cars
        JOIN CarTypes ON Cars.type_id = CarTypes.type_id
        JOIN Companies ON Cars.company_id = Companies.company_id
        WHERE 1=1
    '''
    params = []
    if price_min:
        query += ' AND Cars.price_per_day >= %s'
        params.append(price_min)
    if price_max:
        query += ' AND Cars.price_per_day <= %s'
        params.append(price_max)
    if company:
        query += ' AND Companies.company_name = %s'
        params.append(company)
    if car_type:
        query += ' AND CarTypes.type_name = %s'
        params.append(car_type)
    if location:
        query += ' AND (Cars.from_location LIKE %s OR Cars.to_location LIKE %s)'
        params.append(f'%{location}%')
        params.append(f'%{location}%')

    if sort_price:
        if sort_price == 'asc':
            query += ' ORDER BY Cars.price_per_day ASC'
        elif sort_price == 'desc':
            query += ' ORDER BY Cars.price_per_day DESC'

    try:
        cursor.execute(query, params)
        cars = cursor.fetchall()

        cursor.execute('SELECT company_name FROM Companies')
        companies = cursor.fetchall()

        cursor.execute('SELECT type_name FROM CarTypes')
        car_types = cursor.fetchall()

        return render_template('cars.html', cars=cars, companies=companies, car_types=car_types)
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        flash('Database error occurred. Please try again later!', 'danger')
        return redirect(url_for('home'))

@app.route('/booking_details/<int:booking_id>')
def booking_details(booking_id):
    return redirect(url_for('home'))

@app.route('/car_details/<int:car_id>')
def car_details(car_id):
    try:
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.car_number, Cars.stock, Cars.price_per_day, Cars.image_url, 
                   CarTypes.type_name, Companies.company_name, Users.username,
                   Cars.from_location, Cars.to_location
            FROM Cars
            JOIN CarTypes ON Cars.type_id = CarTypes.type_id
            JOIN Companies ON Cars.company_id = Companies.company_id
            JOIN Users ON Cars.owner_id = Users.user_id
            WHERE Cars.car_id = %s
        ''', (car_id,))
        car = cursor.fetchone()
        if not car:
            return jsonify({'error': 'Car not found'}), 404
        car['image_url'] = url_for('static', filename='uploads/' + car['image_url'])
        return jsonify(car)
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        return jsonify({'error': 'Database error occurred'}), 500

@app.route('/customer_report')
def customer_report():
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            cursor.execute('''
                SELECT Bookings.booking_id, Bookings.customer_name, Bookings.email, 
                       user_profile.phone_number, 
                       CONCAT(user_profile.address_line1, ', ', user_profile.address_line2, ', ', user_profile.city, ', ', user_profile.state, ', ', user_profile.country) AS address,
                       Cars.car_name, 
                       CONCAT(Bookings.pickup_date, ' to ', Bookings.dropoff_date) AS booking_period,
                       CONCAT(Bookings.pickup_address, ' to ', Bookings.dropoff_address) AS booking_location
                FROM Bookings
                JOIN Cars ON Bookings.car_id = Cars.car_id
                JOIN Users ON Bookings.user_id = Users.user_id
                JOIN user_profile ON Users.user_id = user_profile.user_id
                WHERE Cars.owner_id = %s
            ''', (session['user_id'],))
            bookings = cursor.fetchall()
            return render_template('customer_report.html', bookings=bookings)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/customer_details')
def customer_details():
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            cursor.execute('''
                SELECT Bookings.booking_id, Bookings.customer_name, Bookings.email, 
                       user_profile.phone_number, 
                       CONCAT(user_profile.address_line1, ', ', user_profile.address_line2, ', ', user_profile.city, ', ', user_profile.state, ', ', user_profile.country) AS address,
                       Cars.car_name, 
                       CONCAT(Bookings.pickup_date, ' to ', Bookings.dropoff_date) AS booking_period,
                       CONCAT(Bookings.pickup_address, ' to ', Bookings.dropoff_address) AS booking_location
                FROM Bookings
                JOIN Cars ON Bookings.car_id = Cars.car_id
                JOIN Users ON Bookings.user_id = Users.user_id
                JOIN user_profile ON Users.user_id = user_profile.user_id
                WHERE Cars.owner_id = %s
            ''', (session['user_id'],))
            bookings = cursor.fetchall()
            print(bookings)
            return render_template('customer_report.html', bookings=bookings)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

@app.route('/cities', methods=['GET'])
def get_cities():
    logging.debug("Fetching cities...")  # Debugging: Log when the endpoint is triggered
    url = "https://api.countrystatecity.in/v1/countries/IN/states/TN/cities"  # Example URL
    headers = {"X-CSCAPI-KEY": "UzJGVjJRVVBjMk9tdmpvSktGRWg2VnFGS1FjOFg4aFNOS3pLWHhYbw=="}  # Replace with your actual API key
    response = requests.get(url, headers=headers)
    try:
        response.raise_for_status()
        cities_data = response.json()
        logging.debug(f"Cities data: {cities_data}")  # Debugging: Log the fetched cities data
        cities = [{"id": city["id"], "name": city["name"]} for city in cities_data]
        return jsonify(cities)
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        return jsonify({"error": "HTTP error occurred"}), 500
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
        return jsonify({"error": "An error occurred"}), 500

@app.route('/api/bookings', methods=['GET'])
def api_bookings():
    return jsonify({'error': 'Unauthorized'}), 401

@app.route('/delete_booking/<int:booking_id>', methods=['POST'])
def delete_booking(booking_id):
    return jsonify(success=False, message='Unauthorized'), 401

@app.route('/delete_company/<int:company_id>', methods=['POST'])
def delete_company(company_id):
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            # First, delete all bookings associated with the company's cars
            cursor.execute('''
                DELETE Bookings FROM Bookings
                JOIN Cars ON Bookings.car_id = Cars.car_id
                WHERE Cars.company_id = %s
            ''', (company_id,))
            conn.commit()
            
            # Then, delete all cars associated with the company
            cursor.execute('DELETE FROM Cars WHERE company_id = %s', (company_id,))
            conn.commit()
            
            # Finally, delete the company
            cursor.execute('DELETE FROM Companies WHERE company_id = %s', (company_id,))
            conn.commit()
            
            return jsonify(success=True)
        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            return jsonify(success=False, message='Database error occurred. Please try again later!', error=str(e))
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify(success=False, message='An unexpected error occurred. Please try again later!', error=str(e))
    return jsonify(success=False, message='Unauthorized'), 401

@app.route('/edit_customer/<int:user_id>', methods=['GET', 'POST'])
def edit_customer(user_id):
    if 'loggedin' in session and session.get('role') == 'admin':
        if request.method == 'POST':
            try:
                username = request.form.get('username')
                email = request.form.get('email')
                role = request.form.get('role')
                phone_number = request.form.get('phone_number')
                address_line1 = request.form.get('address_line1')
                address_line2 = request.form.get('address_line2')
                state = request.form.get('state')
                city = request.form.get('city')
                country = request.form.get('country')
                birthday = request.form.get('birthday')
                gender = request.form.get('gender')

                cursor.execute('''
                    UPDATE users SET username=%s, email=%s, role=%s WHERE user_id=%s
                ''', (username, email, role, user_id))
                cursor.execute('''
                    UPDATE user_profile SET phone_number=%s, address_line1=%s, address_line2=%s, state=%s, city=%s, country=%s, birthday=%s, gender=%s
                    WHERE user_id=%s
                ''', (phone_number, address_line1, address_line2, state, city, country, birthday, gender, user_id))
                conn.commit()

                flash('Customer updated successfully!', 'success')
                return redirect(url_for('customer_report'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        cursor.execute('''
            SELECT users.*, user_profile.* FROM users
            JOIN user_profile ON users.user_id = user_profile.user_id
            WHERE users.user_id = %s
        ''', (user_id,))
        customer = cursor.fetchone()
        return render_template('edit_customer.html', customer=customer)
    return redirect(url_for('login'))

@app.route('/edit_company/<int:company_id>', methods=['GET', 'POST'])
def edit_company(company_id):
    if 'loggedin' in session and session.get('role') == 'admin':
        if request.method == 'POST':
            try:
                company_name = request.form.get('company_name')
                company_description = request.form.get('company_description')

                cursor.execute('''
                    UPDATE Companies SET company_name=%s, company_description=%s WHERE company_id=%s
                ''', (company_name, company_description, company_id))
                conn.commit()

                flash('Company updated successfully!', 'success')
                return redirect(url_for('company_report'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        cursor.execute('SELECT * FROM Companies WHERE company_id = %s', (company_id,))
        company = cursor.fetchone()
        return render_template('add_company.html', company=company)
    return redirect(url_for('login'))

@app.route('/edit_car_type/<int:type_id>', methods=['GET', 'POST'])
def edit_car_type(type_id):
    if 'loggedin' in session and session.get('role') == 'admin':
        if request.method == 'POST':
            try:
                type_name = request.form.get('type_name')
                type_description = request.form.get('type_description')

                cursor.execute('''
                    UPDATE CarTypes SET type_name=%s, type_description=%s WHERE type_id=%s
                ''', (type_name, type_description, type_id))
                conn.commit()

                flash('Car type updated successfully!', 'success')
                return redirect(url_for('car_type_report'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        cursor.execute('SELECT * FROM CarTypes WHERE type_id = %s', (type_id,))
        car_type = cursor.fetchone()
        return render_template('add_car_type.html', car_type=car_type)
    return redirect(url_for('login'))

@app.route('/api/cars', methods=['GET'])
def api_cars():
    if 'loggedin' in session:
        try:
            page = request.args.get('page', 1, type=int)
            per_page = 5
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT Cars.car_id, Cars.car_name, Cars.car_number, Cars.stock, Cars.price_per_day, Cars.image_url, 
                       CarTypes.type_name, Companies.company_name, Users.username,
                       Cars.from_location, Cars.to_location
                FROM Cars
                JOIN CarTypes ON Cars.type_id = CarTypes.type_id
                JOIN Companies ON Cars.company_id = Companies.company_id
                JOIN Users ON Cars.owner_id = Users.user_id
                WHERE Cars.owner_id = %s
                LIMIT %s OFFSET %s
            ''', (session['user_id'], per_page, offset))
            cars = cursor.fetchall()
            cursor.execute('SELECT COUNT(*) FROM Cars WHERE owner_id = %s', (session['user_id'],))
            total = cursor.fetchone()['COUNT(*)']
            return jsonify({
                'cars': cars,
                'total': total,
                'per_page': per_page,
                'page': page
            })
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            return jsonify({'error': 'Database error occurred'}), 500
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify({'error': 'An unexpected error occurred'}), 500
    return jsonify({'error': 'Unauthorized'}), 401

@app.route('/account', methods=['GET', 'POST'])
def account():
    if 'loggedin' in session:
        user_id = session['user_id']
        if request.method == 'POST':
            try:
                # username = request.form.get('username')  # Remove this line to prevent updating the username
                email = request.form.get('email')
                phone_number = request.form.get('phonenumber')
                address_line1 = request.form.get('addressLine1')
                address_line2 = request.form.get('addressLine2')
                state = request.form.get('state')
                city = request.form.get('city')
                country = request.form.get('country')
                birthday = request.form.get('dob')
                gender = request.form.get('gender')
                # Image file handling
                image_filename = None
                if 'picture' in request.files and request.files['picture'].filename:
                    image_file = request.files['picture']
                    if allowed_image_file(image_file.filename):
                        image_filename = secure_filename(image_file.filename)
                        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                    else:
                        flash('Invalid image file format', 'danger')
                        return redirect(url_for('account'))
                else:
                    # If no new image is uploaded, keep the existing image
                    cursor.execute('SELECT profile_picture FROM user_profile WHERE user_id = %s', (user_id,))
                    existing_user = cursor.fetchone()
                    if existing_user:
                        image_filename = existing_user['profile_picture']

                # Update user details
                cursor.execute('''
                    UPDATE users SET email=%s WHERE user_id=%s
                ''', (email, user_id))
                cursor.execute('''
                    UPDATE user_profile SET phone_number=%s, profile_picture=%s, address_line1=%s, address_line2=%s, state=%s, city=%s, country=%s, birthday=%s, gender=%s
                    WHERE user_id=%s
                ''', (phone_number, image_filename, address_line1, address_line2, state, city, country, birthday, gender, user_id))
                conn.commit()

                flash('Account updated successfully!', 'success')
                return redirect(url_for('account'))
            except mysql.connector.Error as e:
                conn.rollback()
                logging.error("Database error: %s", e)
                flash('Database error occurred. Please try again later!', 'danger')
            except Exception as e:
                logging.error("Unexpected error: %s", e)
                flash('An unexpected error occurred. Please try again later!', 'danger')

        try:
            cursor.execute('''
                SELECT users.username, users.email, user_profile.phone_number, user_profile.profile_picture, 
                       user_profile.address_line1, user_profile.address_line2, user_profile.birthday, 
                       user_profile.gender, user_profile.state, user_profile.city, user_profile.country
                FROM users
                JOIN user_profile ON users.user_id = user_profile.user_id
                WHERE users.user_id = %s
            ''', (user_id,))
            user_details = cursor.fetchone()
            return render_template('account.html', user=user_details)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/booking_report')
def booking_report():
    return redirect(url_for('home'))

@app.route('/admin_booking_report')
def admin_booking_report():
    return redirect(url_for('home'))

@app.route('/api/top_picked_cars', methods=['GET'])
def api_top_picked_cars():
    try:
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.price_per_day, Cars.image_url, Companies.company_name
            FROM Cars
            JOIN Companies ON Cars.company_id = Companies.company_id
            ORDER BY Cars.price_per_day DESC
            LIMIT 5
        ''')
        cars = cursor.fetchall()
        print("=======================",cars)
        
        for car in cars:
            car['image_url'] = url_for('static', filename='uploads/' + car['image_url'])
        return jsonify({'cars': cars})
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/api/latest_added_cars', methods=['GET'])
def api_latest_added_cars():
    try:
        cursor.execute('''
            SELECT Cars.car_id, Cars.car_name, Cars.price_per_day, Cars.image_url, Companies.company_name
            FROM Cars
            JOIN Companies ON Cars.company_id = Companies.company_id
            ORDER BY Cars.car_id DESC
            LIMIT 5
        ''')
        cars = cursor.fetchall()
        print("=======================",cars)
        for car in cars:
            car['image_url'] = url_for('static', filename='uploads/' + car['image_url'])
        return jsonify({'cars': cars})
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logging.error("Unexpected error: %s", e)
        return jsonify({'error': 'An unexpected error occurred'}), 500

# @app.route('/delete_car_type/<int:type_id>', methods=['POST'])
# def delete_car_type(type_id):
#     if 'loggedin' in session and session.get('role') == 'admin':
#         try:
#             # First, delete all cars associated with the car type
#             cursor.execute('DELETE FROM Cars WHERE type_id = %s', (type_id,))
#             conn.commit()
            
#             # Then, delete the car type
#             cursor.execute('DELETE FROM CarTypes WHERE type_id = %s', (type_id,))
#             conn.commit()
            
#             return jsonify(success=True)
#         except mysql.connector.Error as e:
#             conn.rollback()
#             logging.error("Database error: %s", e)
#             return jsonify(success(False), message='Database error occurred. Please try again later!', error=str(e))
#         except Exception as e:
#             logging.error("Unexpected error: %s", e)
#             return jsonify(success(False), message='An unexpected error occurred. Please try again later!', error=str(e))
#     return jsonify(success(False), message='Unauthorized'), 401

@app.route('/delete_car/<int:car_id>', methods=['POST'])
def delete_car(car_id):
    if 'loggedin' in session:
        try:
            cursor.execute('DELETE FROM Cars WHERE car_id = %s AND owner_id = %s', (car_id, session['user_id']))
            conn.commit()
            return jsonify(success(True))
        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            return jsonify(success(False), message='Database error occurred. Please try again later!', error=str(e))
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify(success(False), message='An unexpected error occurred. Please try again later!', error=str(e))
    return jsonify(success(False), message='Unauthorized'), 401

@app.route('/update_account', methods=['POST'])
def update_account():
    if 'loggedin' in session:
        user_id = session['user_id']
        try:
            email = request.form.get('email')
            phone_number = request.form.get('phonenumber')
            address_line1 = request.form.get('addressLine1')
            address_line2 = request.form.get('addressLine2')
            state = request.form.get('state')
            city = request.form.get('city')
            country = request.form.get('country')
            birthday = request.form.get('dob')
            gender = request.form.get('gender')
            # Image file handling
            image_filename = None
            if 'picture' in request.files and request.files['picture'].filename:
                image_file = request.files['picture']
                if allowed_image_file(image_file.filename):
                    image_filename = secure_filename(image_file.filename)
                    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
                else:
                    flash('Invalid image file format', 'danger')
                    return redirect(url_for('account'))
            else:
                # If no new image is uploaded, keep the existing image
                cursor.execute('SELECT profile_picture FROM user_profile WHERE user_id = %s', (user_id,))
                existing_user = cursor.fetchone()
                if existing_user:
                    image_filename = existing_user['profile_picture']

            # Update user details
            cursor.execute('''
                UPDATE users SET email=%s WHERE user_id=%s
            ''', (email, user_id))
            cursor.execute('''
                UPDATE user_profile SET phone_number=%s, profile_picture=%s, address_line1=%s, address_line2=%s, state=%s, city=%s, country=%s, birthday=%s, gender=%s
                WHERE user_id=%s
            ''', (phone_number, image_filename, address_line1, address_line2, state, city, country, birthday, gender, user_id))
            conn.commit()

            flash('Account updated successfully!', 'success')
            return redirect(url_for('account'))
        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
    return redirect(url_for('login'))

@app.route('/company_report')
def company_report():
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            user_id = session['user_id']
            print(user_id)
            cursor.execute('''
                SELECT company_id, company_name, company_description
                FROM Companies
                WHERE user_id = %s
            ''', (user_id,))
            companies = cursor.fetchall()
            return render_template('company_report.html', companies=companies)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
    else:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('home'))

@app.route('/car_type_report')
def car_type_report():
    if 'loggedin' in session:
        try:
            cursor.execute('''
                SELECT type_id, type_name, type_description
                FROM CarTypes
                WHERE user_id = %s
            ''', (session['user_id'],))
            car_types = cursor.fetchall()
            return render_template('car_type_report.html', car_types=car_types)
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
            return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/delete_car_type/<int:type_id>', methods=['POST'])
def delete_car_type(type_id):
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            # First, delete all cars associated with the car type
            cursor.execute('DELETE FROM Cars WHERE type_id = %s', (type_id,))
            conn.commit()
            
            # Then, delete the car type
            cursor.execute('DELETE FROM CarTypes WHERE type_id = %s', (type_id,))
            conn.commit()
            
            return jsonify(success(True))
        except mysql.connector.Error as e:
            conn.rollback()
            logging.error("Database error: %s", e)
            return jsonify(success(False), message='Database error occurred. Please try again later!', error=str(e))
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify(success(False), message='An unexpected error occurred. Please try again later!', error=str(e))
    return jsonify(success(False), message='Unauthorized'), 401

@app.route('/api/companies', methods=['GET'])
def api_companies():
    if 'loggedin' in session and session.get('role') == 'admin':
        try:
            page = request.args.get('page', 1, type=int)
            per_page = 5
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT company_id, company_name, company_description
                FROM Companies
                WHERE user_id = %s
                LIMIT %s OFFSET %s
            ''', (session['user_id'], per_page, offset))
            companies = cursor.fetchall()
            cursor.execute('SELECT COUNT(*) FROM Companies WHERE user_id = %s', (session['user_id'],))
            total = cursor.fetchone()['COUNT(*)']
            return jsonify({
                'companies': companies,
                'total': total,
                'per_page': per_page,
                'page': page
            })
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            return jsonify({'error': 'Database error occurred'}), 500
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify({'error': 'An unexpected error occurred'}), 500
    return jsonify({'error': 'Unauthorized'}), 401

@app.route('/api/car_types', methods=['GET'])
def api_car_types():
    if 'loggedin' in session:
        try:
            page = request.args.get('page', 1, type(int))
            per_page = 5
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT type_id, type_name, type_description
                FROM CarTypes
                WHERE user_id = %s
                LIMIT %s OFFSET %s
            ''', (session['user_id'], per_page, offset))
            car_types = cursor.fetchall()
            cursor.execute('SELECT COUNT(*) FROM CarTypes WHERE user_id = %s', (session['user_id'],))
            total = cursor.fetchone()['COUNT(*)']
            return jsonify({
                'car_types': car_types,
                'total': total,
                'per_page': per_page,
                'page': page
            })
        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            return jsonify({'error': 'Database error occurred'}), 500
        except Exception as e:
            logging.error("Unexpected error: %s", e)
            return jsonify({'error': 'An unexpected error occurred'}), 500
    return jsonify({'error': 'Unauthorized'}), 401

# @app.route('/view_company/<int:company_id>')
# def view_company(company_id):
#     if 'loggedin' in session and session.get('role') == 'admin':
#         try:
#             cursor.execute('SELECT * FROM Companies WHERE company_id = %s', (company_id,))
#             company = cursor.fetchone()
#             if not company:
#                 flash('Company not found!', 'danger')
#                 return redirect(url_for('company_report'))
#             return render_template('view_company.html', company=company)
#         except mysql.connector.Error as e:
#             logging.error("Database error: %s", e)
#             flash('Database error occurred. Please try again later!', 'danger')
#             return redirect(url_for('company_report'))
#         except Exception as e:
#             logging.error("Unexpected error: %s", e)
#             flash('An unexpected error occurred. Please try again later!', 'danger')
#             return redirect(url_for('company_report'))
#     return redirect(url_for('login'))

def get_booking_details(booking_id):
    try:
        cursor.execute('''
            SELECT Bookings.booking_id, Bookings.customer_name, Bookings.email, 
                   CONCAT(Bookings.pickup_date, ' to ', Bookings.dropoff_date) AS booking_period,
                   CONCAT(Bookings.pickup_address, ' to ', Bookings.dropoff_address) AS booking_location,
                   Cars.car_id, Cars.car_name, Cars.car_number, Cars.price_per_day, Cars.image_url AS car_image_url,
                   CarTypes.type_name AS car_type, Companies.company_name,
                   Users.username AS owner_username, user_profile.phone_number AS owner_phone_number
            FROM Bookings
            JOIN Cars ON Bookings.car_id = Cars.car_id
            JOIN CarTypes ON Cars.type_id = CarTypes.type_id
            JOIN Companies ON Cars.company_id = Companies.company_id
            JOIN Users ON Cars.owner_id = Users.user_id
            JOIN user_profile ON Users.user_id = user_profile.user_id
            WHERE Bookings.booking_id = %s
        ''', (booking_id,))
        return cursor.fetchone()
    except mysql.connector.Error as e:
        logging.error("Database error: %s", e)
        return None

@app.route('/api/booking_details/<int:booking_id>')
def api_booking_details(booking_id):
    return jsonify({'error': 'Unauthorized'}), 401

@app.route('/payment', methods=['POST'])
def payment():
    try:
        # Create a new Stripe Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Car Sharing Booking',
                    },
                    'unit_amount': int(request.form['amount']),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cancel', _external=True),
        )
        return redirect(session.url, code=303)
    except Exception as e:
        logging.error("Error creating Stripe session: %s", e)
        return str(e)

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/cancel')
def cancel():
    return render_template('cancel.html')

@app.route('/payment_page/<int:car_id>', methods=['GET'])
def payment_page(car_id):
    if 'loggedin' in session:
        try:
            pickup_date = request.args.get('pickup_date')
            dropoff_date = request.args.get('dropoff_date')

            # Validate date fields
            if not pickup_date or not dropoff_date:
                flash('Pickup date and dropoff date are required.', 'danger')
                return redirect(url_for('book_car'))

            # Fetch car details
            cursor.execute('''
                SELECT Cars.car_id, Cars.car_name, Cars.price_per_day
                FROM Cars
                WHERE Cars.car_id = %s
            ''', (car_id,))
            car = cursor.fetchone()

            if not car:
                flash('Car not found!', 'danger')
                return redirect(url_for('book_car'))

            # Calculate total amount
            pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d')
            dropoff_date_obj = datetime.strptime(dropoff_date, '%Y-%m-%d')
            total_days = (dropoff_date_obj - pickup_date_obj).days
            total_amount = int(car['price_per_day'] * total_days * 100)  # Stripe expects amount in cents

            # Render the payment page with payment details
            return render_template('payment.html', car=car, pickup_date=pickup_date, dropoff_date=dropoff_date, total_days=total_days, total_amount=total_amount)

        except mysql.connector.Error as e:
            logging.error("Database error: %s", e)
            flash('Database error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

        except Exception as e:
            logging.error("Unexpected error: %s", e)
            flash('An unexpected error occurred. Please try again later!', 'danger')
            return redirect(url_for('book_car'))

    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
