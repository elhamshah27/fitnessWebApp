# ⚡ Calquate - Calculate Your Calories

**Live site: [calquate.org](https://calquate.org)**

A modern calorie calculator and nutrition tracking web application built with Flask. Calculate your calories, track your macros, and transform your life.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ⚡ Features

### 🔐 User Authentication
- Secure registration and login with password hashing
- Session-based authentication
- User profiles with customizable fitness settings

### 📊 Macro Tracking
- Track calories, protein, carbs, and fat
- Daily food diary organized by meals
- Visual progress indicators and dashboards

### 🔍 Food Search
- Search thousands of foods using Open Food Facts API
- Detailed nutrition information per 100g
- Easy logging with customizable serving sizes

### 📷 Barcode Scanner
- Scan product barcodes using your camera
- Instant nutrition lookup
- Manual barcode entry option

### 🧮 BMI & BMR Calculator
- Calculate Body Mass Index (BMI)
- Calculate Basal Metabolic Rate (BMR)
- Get Total Daily Energy Expenditure (TDEE)
- Calorie recommendations for different goals

### 📱 Modern UI
- Dark theme with electric gold accents
- Responsive design for mobile and desktop
- Smooth animations and transitions

## 🚀 Installation

### Prerequisites
- Python 3.11 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/calquate.git
   cd calquate
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set environment variables (optional but recommended for production)**
   ```bash
   # Windows
   set SECRET_KEY=your-super-secret-key
   
   # macOS/Linux
   export SECRET_KEY=your-super-secret-key
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

6. **Open in browser**
   Navigate to `http://localhost:5000`

## 🌐 Deployment

### Using Gunicorn (Linux/macOS)
```bash
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

### Using Waitress (Windows)
```bash
pip install waitress
waitress-serve --port=8000 main:app
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

## 📡 API Endpoints

### Authentication
- `POST /login` - User login
- `POST /register` - User registration
- `GET /logout` - User logout

### Food API
- `GET /api/food/search?q={query}` - Search foods
- `GET /api/food/barcode/{barcode}` - Lookup by barcode
- `POST /api/food/log` - Log food to diary
- `DELETE /api/food/log/{id}` - Delete food log entry

### Pages
- `/` - Home page
- `/dashboard` - User dashboard
- `/food` - Food search
- `/barcode` - Barcode scanner
- `/diary` - Food diary
- `/calculator` - BMI/BMR calculator
- `/profile` - User profile

## 🛠 Tech Stack

- **Backend**: Flask, SQLAlchemy, Werkzeug
- **Database**: SQLite (default), PostgreSQL compatible
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **APIs**: Open Food Facts (free, no API key required)
- **Barcode Scanning**: html5-qrcode library
- **Fonts**: Syne, Inter

## 📁 Project Structure

```
calquate/
├── main.py              # Flask application
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── instance/
│   └── database.db     # SQLite database
├── static/
│   ├── style.css       # Main stylesheet
│   └── food-placeholder.svg
├── templates/
│   ├── base.html       # Base template with logo
│   ├── index.html      # Home page
│   ├── login.html      # Login page
│   ├── register.html   # Registration page
│   ├── dashboard.html  # User dashboard
│   ├── profile.html    # User profile
│   ├── calculator.html # BMI/BMR calculator
│   ├── calculator_results.html
│   ├── food_search.html
│   ├── barcode_scanner.html
│   ├── diary.html      # Food diary
│   ├── 404.html        # Error page
│   └── 500.html        # Error page
└── venv/               # Virtual environment
```

## 🔒 Security

- Passwords hashed using Werkzeug's security functions
- Session-based authentication with configurable lifetime
- Always use HTTPS in production
- Change the default SECRET_KEY in production

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- [Open Food Facts](https://world.openfoodfacts.org/) for their free food database API
- [html5-qrcode](https://github.com/mebjas/html5-qrcode) for barcode scanning
- Flask community for the excellent framework

---

**⚡ Calquate** - Calculate your calories. Transform your life.
