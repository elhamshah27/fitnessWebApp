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
# For Vercel: Use Vercel Postgres or external database
# SQLite won't work on Vercel (read-only filesystem)
# Get connection string from Vercel Postgres dashboard
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    # Fallback to SQLite for local development only
    database_url = 'sqlite:///database.db'
    
# Convert Vercel Postgres URL format if needed
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# API Keys - Get free keys from:
# Edamam: https://developer.edamam.com/edamam-nutrition-api (Free tier: 10 calls/minute)
# Spoonacular: https://spoonacular.com/food-api (Free tier: 150 points/day)
EDAMAM_APP_ID = os.environ.get('EDAMAM_APP_ID', 'demo_id')  # Replace with your app ID
EDAMAM_APP_KEY = os.environ.get('EDAMAM_APP_KEY', 'demo_key')  # Replace with your app key
SPOONACULAR_API_KEY = os.environ.get('SPOONACULAR_API_KEY', 'demo_key')  # Replace with your API key

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
# Only create tables if not in Vercel serverless environment
# (Tables should be created via migrations or manually on Vercel Postgres)
if not os.environ.get('VERCEL'):
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            # Silently fail in serverless - tables should exist already
            pass


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

@app.route("/food")
@login_required
def food_search():
    user = get_current_user()
    return render_template("food_search.html", user=user)


@app.route("/api/food/search")
@login_required
def api_food_search():
    """Search for food using multiple APIs (USDA + Open Food Facts)"""
    query = request.args.get('q', '').strip().lower()
    
    if not query:
        return jsonify({'products': []})
    
    products = []
    
    # Search USDA FoodData Central (includes fast food, raw ingredients, branded items)
    try:
        # Prioritize foundation and SR Legacy foods (generic foods) 
        usda_url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={query}&pageSize=25&dataType=Foundation,SR%20Legacy,Survey%20(FNDDS),Branded&api_key=DEMO_KEY"
        usda_response = requests.get(usda_url, timeout=8)
        
        if usda_response.status_code == 200:
            usda_data = usda_response.json()
            
            for food in usda_data.get('foods', []):
                nutrients = {n['nutrientName']: n['value'] for n in food.get('foodNutrients', [])}
                
                data_type = food.get('dataType', '')
                brand = food.get('brandOwner', '') or food.get('brandName', '')
                
                # Label generic foods clearly
                if data_type in ['Foundation', 'SR Legacy']:
                    brand = 'Generic'
                elif data_type == 'Survey (FNDDS)':
                    brand = 'USDA Standard'
                elif not brand:
                    brand = 'Branded'
                
                name = food.get('description', 'Unknown')
                
                # Skip items with no name or very long names (usually junk data)
                if not name or name == 'Unknown' or len(name) > 100:
                    continue
                
                # Calculate relevance score (higher = more relevant)
                name_lower = name.lower()
                relevance = 0
                
                # Exact match gets highest priority
                if name_lower == query:
                    relevance = 100
                # Starts with query
                elif name_lower.startswith(query):
                    relevance = 80
                # Query is a significant part of name
                elif query in name_lower and len(query) > len(name_lower) * 0.3:
                    relevance = 60
                # Generic foods get priority
                if data_type in ['Foundation', 'SR Legacy']:
                    relevance += 30
                elif data_type == 'Survey (FNDDS)':
                    relevance += 20
                # Shorter names are usually more generic
                if len(name) < 30:
                    relevance += 10
                
                products.append({
                    'name': name,
                    'brand': brand,
                    'barcode': food.get('gtinUpc', ''),
                    'image': '',
                    'serving_size': '100g',
                    'calories': nutrients.get('Energy', 0) or 0,
                    'protein': nutrients.get('Protein', 0) or 0,
                    'carbs': nutrients.get('Carbohydrate, by difference', 0) or 0,
                    'fat': nutrients.get('Total lipid (fat)', 0) or 0,
                    'fiber': nutrients.get('Fiber, total dietary', 0) or 0,
                    'sugar': nutrients.get('Sugars, total including NLEA', nutrients.get('Sugars, total', 0)) or 0,
                    'sodium': nutrients.get('Sodium, Na', 0) or 0,
                    '_relevance': relevance,
                    '_source': 'usda'
                })
    except Exception as e:
        print(f"USDA API error: {e}")
    
    # Search Open Food Facts (packaged store items with barcodes)
    try:
        off_url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=15"
        off_response = requests.get(off_url, timeout=5)
        
        if off_response.status_code == 200:
            off_data = off_response.json()
            
            for product in off_data.get('products', []):
                nutriments = product.get('nutriments', {})
                name = product.get('product_name', '')
                
                # Skip items with no name
                if not name or len(name) > 100:
                    continue
                
                # Calculate relevance
                name_lower = name.lower()
                relevance = 0
                if name_lower == query:
                    relevance = 90
                elif name_lower.startswith(query):
                    relevance = 70
                elif query in name_lower:
                    relevance = 40
                
                products.append({
                    'name': name,
                    'brand': product.get('brands', 'Store Brand') or 'Store Brand',
                    'barcode': product.get('code', ''),
                    'image': product.get('image_small_url', ''),
                    'serving_size': product.get('serving_size', '100g'),
                    'calories': nutriments.get('energy-kcal_100g', nutriments.get('energy-kcal', 0)) or 0,
                    'protein': nutriments.get('proteins_100g', nutriments.get('proteins', 0)) or 0,
                    'carbs': nutriments.get('carbohydrates_100g', nutriments.get('carbohydrates', 0)) or 0,
                    'fat': nutriments.get('fat_100g', nutriments.get('fat', 0)) or 0,
                    'fiber': nutriments.get('fiber_100g', nutriments.get('fiber', 0)) or 0,
                    'sugar': nutriments.get('sugars_100g', nutriments.get('sugars', 0)) or 0,
                    'sodium': (nutriments.get('sodium_100g', nutriments.get('sodium', 0)) or 0) * 1000 if nutriments.get('sodium_100g') else 0,
                    '_relevance': relevance,
                    '_source': 'off'
                })
    except Exception as e:
        print(f"OpenFoodFacts error: {e}")
    
    # Sort by relevance (highest first), then by name length (shorter = more generic)
    products.sort(key=lambda x: (-x.get('_relevance', 0), len(x.get('name', ''))))
    
    # Remove internal fields and limit results
    for p in products:
        p.pop('_relevance', None)
        p.pop('_source', None)
    
    return jsonify({'products': products[:20]})


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
    if not os.environ.get('VERCEL'):
        with app.app_context():
            try:
                db.create_all()
            except Exception as e:
                pass
    # Only run in debug mode for local development
    # In production, use: gunicorn main:app
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
