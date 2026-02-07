import os
import requests
from flask import Flask, redirect, url_for, render_template, request, session, flash, jsonify
from datetime import timedelta, datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


class Base(DeclarativeBase):
    pass


app = Flask(__name__)

# Add min/max to Jinja2 templates
app.jinja_env.globals.update(min=min, max=max)

# Configuration - Use environment variables in production
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.permanent_session_lifetime = timedelta(days=5)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# API Keys - Get free keys from:
# Edamam: https://developer.edamam.com/edamam-nutrition-api (Free tier: 10 calls/minute)
# Spoonacular: https://spoonacular.com/food-api (Free tier: 150 points/day)
# Nutritionix: https://www.nutritionix.com/business/api (popular NLP food API)
EDAMAM_APP_ID = os.environ.get('EDAMAM_APP_ID', 'demo_id')  # Replace with your app ID
EDAMAM_APP_KEY = os.environ.get('EDAMAM_APP_KEY', 'demo_key')  # Replace with your app key
SPOONACULAR_API_KEY = os.environ.get('SPOONACULAR_API_KEY', 'demo_key')  # Replace with your API key
NUTRITIONIX_APP_ID = os.environ.get('NUTRITIONIX_APP_ID', 'demo_id')
NUTRITIONIX_APP_KEY = os.environ.get('NUTRITIONIX_APP_KEY', 'demo_key')

db = SQLAlchemy(model_class=Base)
db.init_app(app)


# ============== DATABASE MODELS ==============

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)  # Hashed password
    email = db.Column(db.String(80), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # User profile data
    height = db.Column(db.Float, nullable=True)  # cm
    weight = db.Column(db.Float, nullable=True)  # kg
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    activity_level = db.Column(db.Float, default=1.2)
    calorie_goal = db.Column(db.Integer, nullable=True)
    
    # Relationships
    food_logs = db.relationship('FoodLog', backref='user', lazy=True, cascade='all, delete-orphan')

    def __init__(self, username, password, email):
        self.username = username
        self.password = generate_password_hash(password)
        self.email = email

    def check_password(self, password):
        return check_password_hash(self.password, password)
    
    def calculate_bmr(self):
        if not all([self.weight, self.height, self.age, self.gender]):
            return None
        if self.gender == 'male':
            return 88.362 + (13.397 * self.weight) + (4.799 * self.height) - (5.677 * self.age)
        else:
            return 447.593 + (9.247 * self.weight) + (3.098 * self.height) - (4.330 * self.age)
    
    def calculate_tdee(self):
        bmr = self.calculate_bmr()
        if bmr:
            return bmr * self.activity_level
        return None


class FoodLog(db.Model):
    __tablename__ = 'food_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    meal_type = db.Column(db.String(20), default='snack')  # breakfast, lunch, dinner, snack
    
    # Food info
    food_name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(200), nullable=True)
    barcode = db.Column(db.String(50), nullable=True)
    serving_size = db.Column(db.Float, default=1.0)
    serving_unit = db.Column(db.String(50), default='serving')
    
    # Nutrition per serving
    calories = db.Column(db.Float, default=0)
    protein = db.Column(db.Float, default=0)  # grams
    carbs = db.Column(db.Float, default=0)    # grams
    fat = db.Column(db.Float, default=0)      # grams
    fiber = db.Column(db.Float, default=0)    # grams
    sugar = db.Column(db.Float, default=0)    # grams
    sodium = db.Column(db.Float, default=0)   # mg
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Create all tables after models are defined
with app.app_context():
    db.create_all()


# ============== DECORATORS ==============

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        # Verify user still exists
        user = get_current_user()
        if user is None:
            flash("Please log in again.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user is None:
            # User was deleted, clear session
            session.clear()
        return user
    return None


# ============== ROUTES ==============

@app.route("/")
def home():
    user = get_current_user()
    return render_template("index.html", user=user)


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    today = date.today()
    
    # Get today's food logs
    today_logs = FoodLog.query.filter_by(user_id=user.id, date=today).all()
    
    # Calculate totals
    totals = {
        'calories': sum(log.calories * log.serving_size for log in today_logs),
        'protein': sum(log.protein * log.serving_size for log in today_logs),
        'carbs': sum(log.carbs * log.serving_size for log in today_logs),
        'fat': sum(log.fat * log.serving_size for log in today_logs),
        'fiber': sum(log.fiber * log.serving_size for log in today_logs),
    }
    
    # Get user's calorie goal or calculate from TDEE
    calorie_goal = user.calorie_goal or (user.calculate_tdee() if user.calculate_tdee() else 2000)
    
    # Group logs by meal type
    meals = {
        'breakfast': [log for log in today_logs if log.meal_type == 'breakfast'],
        'lunch': [log for log in today_logs if log.meal_type == 'lunch'],
        'dinner': [log for log in today_logs if log.meal_type == 'dinner'],
        'snack': [log for log in today_logs if log.meal_type == 'snack'],
    }
    
    return render_template("dashboard.html", 
                         user=user, 
                         totals=totals, 
                         calorie_goal=calorie_goal,
                         meals=meals,
                         today=today)


@app.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    
    if request.method == 'POST':
        user.email = request.form.get('email', user.email)
        user.height = float(request.form.get('height')) if request.form.get('height') else None
        user.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        user.age = int(request.form.get('age')) if request.form.get('age') else None
        user.gender = request.form.get('gender')
        user.activity_level = float(request.form.get('activity', 1.2))
        user.calorie_goal = int(request.form.get('calorie_goal')) if request.form.get('calorie_goal') else None
        
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))
    
    return render_template("profile.html", user=user)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session.permanent = True
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Welcome back, " + user.username + "!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")
    
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/register", methods=['GET', 'POST'])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        # Validation
        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")
        
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")
        
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return render_template("register.html")
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
            return render_template("register.html")
        
        new_user = User(username, password, email)
        db.session.add(new_user)
        db.session.commit()
        
        session.permanent = True
        session["user_id"] = new_user.id
        session["username"] = new_user.username
        
        flash("Account created! Let's set up your profile.", "success")
        return redirect(url_for("profile"))
    
    return render_template("register.html")


# ============== BMI/BMR CALCULATOR ==============

@app.route('/calculator')
def calculator():
    user = get_current_user()
    return render_template("calculator.html", user=user)


@app.route('/calculator/results', methods=['POST'])
def calculator_results():
    user = get_current_user()
    
    try:
        height = float(request.form['height'])
        weight = float(request.form['weight'])
        age = int(request.form['age'])
        gender = request.form['gender']
        activity_factor = float(request.form['activity'])
        
        # Calculate BMI
        bmi = 10000 * (weight / (height * height))
        
        # Calculate BMR (Mifflin-St Jeor)
        if gender == 'male':
            bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
        else:
            bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)
        
        tdee = bmr * activity_factor
        
        # Classify BMI
        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal weight"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"
        
        # If user is logged in, offer to save these values
        return render_template("calculator_results.html", 
                             user=user,
                             bmi=round(bmi, 1),
                             bmr=round(bmr, 0),
                             tdee=round(tdee, 0),
                             category=category,
                             height=height,
                             weight=weight,
                             age=age,
                             gender=gender,
                             activity=activity_factor)
    except (ValueError, KeyError) as e:
        flash("Please enter valid values.", "error")
        return redirect(url_for("calculator"))


@app.route('/save_stats', methods=['POST'])
@login_required
def save_stats():
    user = get_current_user()
    
    user.height = float(request.form.get('height', 0))
    user.weight = float(request.form.get('weight', 0))
    user.age = int(request.form.get('age', 0))
    user.gender = request.form.get('gender')
    user.activity_level = float(request.form.get('activity', 1.2))
    
    tdee = float(request.form.get('tdee', 2000))
    user.calorie_goal = int(tdee)
    
    db.session.commit()
    flash("Your stats have been saved to your profile!", "success")
    return redirect(url_for("dashboard"))


# ============== FOOD SEARCH & TRACKING ==============

# Built-in common foods (per 100g) so generic items always appear even without API keys
COMMON_FOODS = [
    # Proteins
    {'name': 'Chicken Breast', 'brand': 'Generic', 'calories': 165, 'protein': 31, 'carbs': 0, 'fat': 3.6, 'fiber': 0, 'sugar': 0, 'sodium': 74},
    {'name': 'Chicken Thigh', 'brand': 'Generic', 'calories': 209, 'protein': 26, 'carbs': 0, 'fat': 10.9, 'fiber': 0, 'sugar': 0, 'sodium': 84},
    {'name': 'Ground Beef (80/20)', 'brand': 'Generic', 'calories': 254, 'protein': 17.2, 'carbs': 0, 'fat': 20, 'fiber': 0, 'sugar': 0, 'sodium': 75},
    {'name': 'Ground Beef (90/10)', 'brand': 'Generic', 'calories': 176, 'protein': 20, 'carbs': 0, 'fat': 10, 'fiber': 0, 'sugar': 0, 'sodium': 66},
    {'name': 'Ground Turkey', 'brand': 'Generic', 'calories': 149, 'protein': 19.5, 'carbs': 0, 'fat': 7.6, 'fiber': 0, 'sugar': 0, 'sodium': 76},
    {'name': 'Salmon', 'brand': 'Generic', 'calories': 208, 'protein': 20, 'carbs': 0, 'fat': 13, 'fiber': 0, 'sugar': 0, 'sodium': 59},
    {'name': 'Tuna (Canned)', 'brand': 'Generic', 'calories': 116, 'protein': 25.5, 'carbs': 0, 'fat': 0.8, 'fiber': 0, 'sugar': 0, 'sodium': 338},
    {'name': 'Egg (Whole)', 'brand': 'Generic', 'calories': 155, 'protein': 13, 'carbs': 1.1, 'fat': 11, 'fiber': 0, 'sugar': 1.1, 'sodium': 124},
    {'name': 'Tofu', 'brand': 'Generic', 'calories': 76, 'protein': 8, 'carbs': 1.9, 'fat': 4.8, 'fiber': 0.3, 'sugar': 0.6, 'sodium': 7},

    # Fruits
    {'name': 'Banana', 'brand': 'Generic', 'calories': 89, 'protein': 1.1, 'carbs': 23, 'fat': 0.3, 'fiber': 2.6, 'sugar': 12, 'sodium': 1},
    {'name': 'Apple', 'brand': 'Generic', 'calories': 52, 'protein': 0.3, 'carbs': 14, 'fat': 0.2, 'fiber': 2.4, 'sugar': 10, 'sodium': 1},
    {'name': 'Orange', 'brand': 'Generic', 'calories': 47, 'protein': 0.9, 'carbs': 12, 'fat': 0.1, 'fiber': 2.4, 'sugar': 9, 'sodium': 0},
    {'name': 'Strawberry', 'brand': 'Generic', 'calories': 32, 'protein': 0.7, 'carbs': 7.7, 'fat': 0.3, 'fiber': 2, 'sugar': 4.9, 'sodium': 1},
    {'name': 'Mango', 'brand': 'Generic', 'calories': 60, 'protein': 0.8, 'carbs': 15, 'fat': 0.4, 'fiber': 1.6, 'sugar': 14, 'sodium': 1},
    {'name': 'Avocado', 'brand': 'Generic', 'calories': 160, 'protein': 2, 'carbs': 9, 'fat': 15, 'fiber': 7, 'sugar': 0.7, 'sodium': 7},

    # Vegetables
    {'name': 'Broccoli', 'brand': 'Generic', 'calories': 34, 'protein': 2.8, 'carbs': 7, 'fat': 0.4, 'fiber': 2.6, 'sugar': 1.7, 'sodium': 33},
    {'name': 'Spinach', 'brand': 'Generic', 'calories': 23, 'protein': 2.9, 'carbs': 3.6, 'fat': 0.4, 'fiber': 2.2, 'sugar': 0.4, 'sodium': 79},
    {'name': 'Carrot', 'brand': 'Generic', 'calories': 41, 'protein': 0.9, 'carbs': 10, 'fat': 0.2, 'fiber': 2.8, 'sugar': 4.7, 'sodium': 69},
    {'name': 'Sweet Potato', 'brand': 'Generic', 'calories': 86, 'protein': 1.6, 'carbs': 20, 'fat': 0.1, 'fiber': 3, 'sugar': 4.2, 'sodium': 55},

    # Grains & Carbs
    {'name': 'White Rice (Cooked)', 'brand': 'Generic', 'calories': 130, 'protein': 2.7, 'carbs': 28, 'fat': 0.3, 'fiber': 0.4, 'sugar': 0, 'sodium': 1},
    {'name': 'Brown Rice (Cooked)', 'brand': 'Generic', 'calories': 112, 'protein': 2.6, 'carbs': 24, 'fat': 0.9, 'fiber': 1.8, 'sugar': 0.4, 'sodium': 1},
    {'name': 'Pasta (Cooked)', 'brand': 'Generic', 'calories': 131, 'protein': 5, 'carbs': 25, 'fat': 1.1, 'fiber': 1.8, 'sugar': 0.6, 'sodium': 1},
    {'name': 'Bread (Whole Wheat)', 'brand': 'Generic', 'calories': 247, 'protein': 13, 'carbs': 41, 'fat': 3.4, 'fiber': 7, 'sugar': 6, 'sodium': 400},
    {'name': 'Oatmeal (Cooked)', 'brand': 'Generic', 'calories': 68, 'protein': 2.4, 'carbs': 12, 'fat': 1.4, 'fiber': 1.7, 'sugar': 0.5, 'sodium': 49},
    {'name': 'Quinoa (Cooked)', 'brand': 'Generic', 'calories': 120, 'protein': 4.4, 'carbs': 21, 'fat': 1.9, 'fiber': 2.8, 'sugar': 0.9, 'sodium': 7},

    # Dairy
    {'name': 'Milk (Whole)', 'brand': 'Generic', 'calories': 61, 'protein': 3.2, 'carbs': 4.8, 'fat': 3.3, 'fiber': 0, 'sugar': 5, 'sodium': 43},
    {'name': 'Greek Yogurt', 'brand': 'Generic', 'calories': 59, 'protein': 10, 'carbs': 3.6, 'fat': 0.7, 'fiber': 0, 'sugar': 3.2, 'sodium': 36},
    {'name': 'Cheddar Cheese', 'brand': 'Generic', 'calories': 403, 'protein': 23, 'carbs': 1.3, 'fat': 33, 'fiber': 0, 'sugar': 0.5, 'sodium': 621},

    # Nuts & Seeds
    {'name': 'Almonds', 'brand': 'Generic', 'calories': 579, 'protein': 21, 'carbs': 22, 'fat': 50, 'fiber': 12.5, 'sugar': 4.4, 'sodium': 1},
    {'name': 'Peanut Butter', 'brand': 'Generic', 'calories': 588, 'protein': 25, 'carbs': 20, 'fat': 50, 'fiber': 6, 'sugar': 9, 'sodium': 459},

    # Fast Food (sample)
    {'name': 'Big Mac', 'brand': "McDonald's", 'calories': 563, 'protein': 26, 'carbs': 45, 'fat': 33, 'fiber': 3.5, 'sugar': 9, 'sodium': 1040},
    {'name': 'Whopper', 'brand': 'Burger King', 'calories': 657, 'protein': 28, 'carbs': 49, 'fat': 40, 'fiber': 2, 'sugar': 11, 'sodium': 980},
    {'name': 'Chicken McNuggets (6pc)', 'brand': "McDonald's", 'calories': 250, 'protein': 14, 'carbs': 15, 'fat': 15, 'fiber': 1, 'sugar': 0, 'sodium': 510},
    {'name': 'Cheeseburger', 'brand': 'Generic Fast Food', 'calories': 303, 'protein': 15, 'carbs': 27, 'fat': 14, 'fiber': 1.3, 'sugar': 5, 'sodium': 714},
    {'name': 'Pizza (Cheese)', 'brand': 'Generic', 'calories': 266, 'protein': 11, 'carbs': 33, 'fat': 10, 'fiber': 2.3, 'sugar': 3.6, 'sodium': 598},
]


@app.route("/food")
@login_required
def food_search():
    user = get_current_user()
    return render_template("food_search.html", user=user)


@app.route("/api/food/search")
@login_required
def api_food_search():
    """
    Multi-source food search:
    1) Built-in COMMON_FOODS (instant, no network)
    2) Nutritionix (if keys set) - great NLP/restaurant coverage
    3) Edamam (if keys set) - large generic database
    4) Open Food Facts fallback for barcoded items
    """
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'products': []})

    query_lower = query.lower()
    products = []

    # --- STEP 1: Built-in DB (always on) ---
    for food in COMMON_FOODS:
        name_lower = food['name'].lower()
        if query_lower in name_lower:
            relevance = 0
            if name_lower == query_lower:
                relevance = 300
            elif name_lower.startswith(query_lower):
                relevance = 250
            else:
                relevance = 170
            if len(food['name']) < 20:
                relevance += 15
            if food['brand'] == 'Generic':
                relevance += 20
            products.append({
                'name': food['name'],
                'brand': food['brand'],
                'barcode': '',
                'image': '',
                'serving_size': '100g',
                'calories': round(food['calories'], 1),
                'protein': round(food['protein'], 1),
                'carbs': round(food['carbs'], 1),
                'fat': round(food['fat'], 1),
                'fiber': round(food['fiber'], 1),
                'sugar': round(food['sugar'], 1),
                'sodium': round(food['sodium'], 1),
                '_relevance': relevance,
                '_source': 'local'
            })

    # --- STEP 2: Nutritionix (NLP, restaurant + branded) ---
    if NUTRITIONIX_APP_ID != 'demo_id' and NUTRITIONIX_APP_KEY != 'demo_key':
        try:
            headers = {
                'x-app-id': NUTRITIONIX_APP_ID,
                'x-app-key': NUTRITIONIX_APP_KEY,
                'Content-Type': 'application/json'
            }
            nx_resp = requests.post(
                "https://trackapi.nutritionix.com/v2/natural/nutrients",
                headers=headers,
                json={"query": query},
                timeout=6
            )
            if nx_resp.status_code == 200:
                nx_data = nx_resp.json()
                for item in nx_data.get('foods', []):
                    name = item.get('food_name', '')
                    if not name:
                        continue
                    name_lower = name.lower()
                    relevance = 0
                    if name_lower == query_lower:
                        relevance = 260
                    elif name_lower.startswith(query_lower):
                        relevance = 220
                    elif query_lower in name_lower:
                        relevance = 180
                    serving_weight = item.get('serving_weight_grams') or 100
                    products.append({
                        'name': name.title(),
                        'brand': item.get('brand_name', 'Generic') or 'Generic',
                        'barcode': item.get('nix_item_id', ''),
                        'image': item.get('photo', {}).get('thumb', ''),
                        'serving_size': f"{serving_weight}g",
                        'calories': round(item.get('nf_calories', 0) or 0, 1),
                        'protein': round(item.get('nf_protein', 0) or 0, 1),
                        'carbs': round(item.get('nf_total_carbohydrate', 0) or 0, 1),
                        'fat': round(item.get('nf_total_fat', 0) or 0, 1),
                        'fiber': round(item.get('nf_dietary_fiber', 0) or 0, 1),
                        'sugar': round(item.get('nf_sugars', 0) or 0, 1),
                        'sodium': round(item.get('nf_sodium', 0) or 0, 1),
                        '_relevance': relevance,
                        '_source': 'nutritionix'
                    })
        except Exception as e:
            print(f"Nutritionix API error: {e}")

    # --- STEP 3: Edamam (generic foods) ---
    if EDAMAM_APP_ID != 'demo_id' and EDAMAM_APP_KEY != 'demo_key':
        try:
            edamam_url = "https://api.edamam.com/api/food-database/v2/parser"
            params = {
                'app_id': EDAMAM_APP_ID,
                'app_key': EDAMAM_APP_KEY,
                'ingr': query,
                'nutrition-type': 'logging'
            }
            edamam_resp = requests.get(edamam_url, params=params, timeout=5)
            if edamam_resp.status_code == 200:
                edamam_data = edamam_resp.json()
                for hint in edamam_data.get('hints', [])[:12]:
                    food = hint.get('food', {})
                    nutrients = food.get('nutrients', {})
                    name = food.get('label', '')
                    if not name:
                        continue
                    name_lower = name.lower()
                    relevance = 0
                    if name_lower == query_lower:
                        relevance = 240
                    elif name_lower.startswith(query_lower):
                        relevance = 210
                    elif query_lower in name_lower:
                        relevance = 170
                    if food.get('categoryLabel') == 'Generic foods':
                        relevance += 20
                    products.append({
                        'name': name.title(),
                        'brand': food.get('brand', 'Generic') or 'Generic',
                        'barcode': '',
                        'image': food.get('image', ''),
                        'serving_size': '100g',
                        'calories': round(nutrients.get('ENERC_KCAL', 0) or 0, 1),
                        'protein': round(nutrients.get('PROCNT', 0) or 0, 1),
                        'carbs': round(nutrients.get('CHOCDF', 0) or 0, 1),
                        'fat': round(nutrients.get('FAT', 0) or 0, 1),
                        'fiber': round(nutrients.get('FIBTG', 0) or 0, 1),
                        'sugar': round(nutrients.get('SUGAR', 0) or 0, 1),
                        'sodium': round(nutrients.get('NA', 0) or 0, 1),
                        '_relevance': relevance,
                        '_source': 'edamam'
                    })
        except Exception as e:
            print(f"Edamam API error: {e}")

    # --- STEP 4: Open Food Facts (fallback for branded/barcode) ---
    if len(products) < 12:  # only call if we still want more variety
        try:
            off_url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                'search_terms': query,
                'search_simple': 1,
                'action': 'process',
                'json': 1,
                'page_size': 15,
                'fields': 'product_name,brands,code,nutriments,image_small_url,serving_size'
            }
            off_resp = requests.get(off_url, params=params, timeout=4)
            if off_resp.status_code == 200:
                off_data = off_resp.json()
                for product in off_data.get('products', []):
                    nutriments = product.get('nutriments', {})
                    name = product.get('product_name', '')
                    if not name or len(name) > 90:
                        continue
                    name_lower = name.lower()
                    relevance = 0
                    if name_lower == query_lower:
                        relevance = 120
                    elif name_lower.startswith(query_lower):
                        relevance = 100
                    elif query_lower in name_lower:
                        relevance = 70
                    products.append({
                        'name': name,
                        'brand': product.get('brands', 'Store Brand') or 'Store Brand',
                        'barcode': product.get('code', ''),
                        'image': product.get('image_small_url', ''),
                        'serving_size': product.get('serving_size', '100g') or '100g',
                        'calories': round(nutriments.get('energy-kcal_100g', 0) or 0, 1),
                        'protein': round(nutriments.get('proteins_100g', 0) or 0, 1),
                        'carbs': round(nutriments.get('carbohydrates_100g', 0) or 0, 1),
                        'fat': round(nutriments.get('fat_100g', 0) or 0, 1),
                        'fiber': round(nutriments.get('fiber_100g', 0) or 0, 1),
                        'sugar': round(nutriments.get('sugars_100g', 0) or 0, 1),
                        'sodium': round((nutriments.get('sodium_100g', 0) or 0) * 1000, 1),
                        '_relevance': relevance,
                        '_source': 'off'
                    })
        except Exception as e:
            print(f"OpenFoodFacts error: {e}")

    # --- Finalize results ---
    products.sort(key=lambda x: (-x.get('_relevance', 0), len(x.get('name', ''))))

    seen = set()
    unique_products = []
    for p in products:
        p.pop('_relevance', None)
        p.pop('_source', None)
        key = (p['name'].lower().strip(), (p.get('brand') or '').lower().strip())
        if key not in seen:
            seen.add(key)
            unique_products.append(p)

    return jsonify({'products': unique_products[:30]})


@app.route("/api/food/barcode/<barcode>")
@login_required
def api_food_barcode(barcode):
    """Look up food by barcode using Open Food Facts API"""
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == 1:
            product = data.get('product', {})
            nutriments = product.get('nutriments', {})
            
            return jsonify({
                'found': True,
                'product': {
                    'name': product.get('product_name', 'Unknown Product'),
                    'brand': product.get('brands', ''),
                    'barcode': barcode,
                    'image': product.get('image_url', ''),
                    'serving_size': product.get('serving_size', '100g'),
                    'calories': nutriments.get('energy-kcal_100g', nutriments.get('energy-kcal', 0)),
                    'protein': nutriments.get('proteins_100g', nutriments.get('proteins', 0)),
                    'carbs': nutriments.get('carbohydrates_100g', nutriments.get('carbohydrates', 0)),
                    'fat': nutriments.get('fat_100g', nutriments.get('fat', 0)),
                    'fiber': nutriments.get('fiber_100g', nutriments.get('fiber', 0)),
                    'sugar': nutriments.get('sugars_100g', nutriments.get('sugars', 0)),
                    'sodium': nutriments.get('sodium_100g', nutriments.get('sodium', 0)) * 1000 if nutriments.get('sodium_100g') else 0,
                }
            })
        else:
            return jsonify({'found': False, 'message': 'Product not found'})
    
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)})


@app.route("/api/food/log", methods=['POST'])
@login_required
def api_log_food():
    """Log food to user's diary"""
    user = get_current_user()
    data = request.json
    
    try:
        food_log = FoodLog(
            user_id=user.id,
            date=datetime.strptime(data.get('date', str(date.today())), '%Y-%m-%d').date(),
            meal_type=data.get('meal_type', 'snack'),
            food_name=data.get('name', 'Unknown'),
            brand=data.get('brand', ''),
            barcode=data.get('barcode', ''),
            serving_size=float(data.get('serving_size', 1)),
            serving_unit=data.get('serving_unit', 'serving'),
            calories=float(data.get('calories', 0)),
            protein=float(data.get('protein', 0)),
            carbs=float(data.get('carbs', 0)),
            fat=float(data.get('fat', 0)),
            fiber=float(data.get('fiber', 0)),
            sugar=float(data.get('sugar', 0)),
            sodium=float(data.get('sodium', 0)),
        )
        
        db.session.add(food_log)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Food logged successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route("/api/food/log/<int:log_id>", methods=['DELETE'])
@login_required
def api_delete_food_log(log_id):
    """Delete a food log entry"""
    user = get_current_user()
    
    log = FoodLog.query.filter_by(id=log_id, user_id=user.id).first()
    
    if log:
        db.session.delete(log)
        db.session.commit()
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'error': 'Log not found'})


@app.route("/barcode")
@login_required
def barcode_scanner():
    user = get_current_user()
    return render_template("barcode_scanner.html", user=user)


@app.route("/diary")
@login_required
def food_diary():
    user = get_current_user()
    
    # Get date from query param or use today
    date_str = request.args.get('date', str(date.today()))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        selected_date = date.today()
    
    # Get food logs for selected date
    logs = FoodLog.query.filter_by(user_id=user.id, date=selected_date).order_by(FoodLog.created_at).all()
    
    # Calculate totals
    totals = {
        'calories': sum(log.calories * log.serving_size for log in logs),
        'protein': sum(log.protein * log.serving_size for log in logs),
        'carbs': sum(log.carbs * log.serving_size for log in logs),
        'fat': sum(log.fat * log.serving_size for log in logs),
        'fiber': sum(log.fiber * log.serving_size for log in logs),
    }
    
    # Group by meal
    meals = {
        'breakfast': [log for log in logs if log.meal_type == 'breakfast'],
        'lunch': [log for log in logs if log.meal_type == 'lunch'],
        'dinner': [log for log in logs if log.meal_type == 'dinner'],
        'snack': [log for log in logs if log.meal_type == 'snack'],
    }
    
    calorie_goal = user.calorie_goal or 2000
    
    return render_template("diary.html", 
                         user=user, 
                         meals=meals, 
                         totals=totals,
                         calorie_goal=calorie_goal,
                         selected_date=selected_date)


# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500


# ============== MAIN ==============

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
