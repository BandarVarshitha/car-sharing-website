-- Create Users Table
CREATE DATABASE IF NOT EXISTS cars;
USE cars;

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,    -- Auto-incrementing user ID
    username VARCHAR(50) NOT NULL UNIQUE,      -- Username (must be unique)
    password VARCHAR(255) NOT NULL,            -- Password (hashed)
    role ENUM('admin', 'user') NOT NULL,       -- Role of the user
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Timestamp when the user is created
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP -- Last update timestamp
);

CREATE TABLE IF NOT EXISTS user_profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    state VARCHAR(100),
    city VARCHAR(100),
    country VARCHAR(100),
    gender ENUM('Male', 'Female'),
    birthday DATE,
    phone_number VARCHAR(20),
    profile_picture VARCHAR(255),
    email VARCHAR(255) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS CarTypes (
    type_id INT PRIMARY KEY AUTO_INCREMENT,
    type_name VARCHAR(255) NOT NULL,
    type_description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS Companies (
    company_id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(255) NOT NULL,
    company_description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS Cars (
    car_id INT PRIMARY KEY AUTO_INCREMENT,
    owner_id INT,
    car_name VARCHAR(255) NOT NULL,
    type_id INT,
    company_id INT,
    stock INT NOT NULL,
    price_per_day DECIMAL(10, 2) NOT NULL,
    image_url VARCHAR(255),
    from_location VARCHAR(100) NOT NULL,
    to_location VARCHAR(100) NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(user_id),
    FOREIGN KEY (type_id) REFERENCES CarTypes(type_id),
    FOREIGN KEY (company_id) REFERENCES Companies(company_id)
);

CREATE TABLE IF NOT EXISTS Bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    car_id INT NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    pickup_date DATE NOT NULL,
    dropoff_date DATE NOT NULL,
    pickup_address VARCHAR(255) NOT NULL,
    dropoff_address VARCHAR(255) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (car_id) REFERENCES Cars(car_id) ON DELETE CASCADE
);
