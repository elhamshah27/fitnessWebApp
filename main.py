import os
import requests
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, render_template, request, session, flash, jsonify
from datetime import timedelta, datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from functools import wraps
from supabase import create_client, Client

load_dotenv()


class Base(DeclarativeBase):
    pass


app = Flask(__name__)

# Add min/max to Jinja2 templates
app.jinja_env.globals.update(min=min, max=max)

# Configuration - Use environment variables in production
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.permanent_session_lifetime = timedelta(days=5)
# For Vercel: Use Supabase Postgres or Vercel Postgres
# SQLite won't work on Vercel (read-only filesystem)
database_url = os.environ.get('DATABASE_POSTGRES_URL') or os.environ.get('DATABASE_URL')
if not database_url:
    # Fallback to SQLite for local development only
    database_url = 'sqlite:///database.db'

# Convert Vercel Postgres URL format if needed
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Supabase client — lazy so missing env vars don't crash startup
_supabase_client: Client | None = None

def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get('SUPABASE_URL', '')
        key = os.environ.get('SUPABASE_KEY', '')
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are not set")
        _supabase_client = create_client(url, key)
    return _supabase_client

# FatSecret API is configured in food_apis.py
# USDA fallback also configured in food_apis.py

db = SQLAlchemy(model_class=Base)
db.init_app(app)


# Database initialization and schema migrations
def init_db():
    """Create tables and handle schema migrations."""
    try:
        with app.app_context():
            # Create all tables that don't exist
            db.create_all()

            # Migrate existing tables (add missing columns)
            with db.engine.begin() as conn:
                is_sqlite = 'sqlite' in str(db.engine.url)

                # Check if supabase_id column exists
                inspector = db.inspect(db.engine)
                try:
                    existing_cols = [col['name'] for col in inspector.get_columns('users')]
                    if 'supabase_id' not in existing_cols:
                        # Column is missing, add it
                        if is_sqlite:
                            conn.exec_driver_sql(
                                'ALTER TABLE users ADD COLUMN supabase_id VARCHAR(100) UNIQUE'
                            )
                        else:
                            conn.exec_driver_sql(
                                'ALTER TABLE users ADD COLUMN IF NOT EXISTS supabase_id VARCHAR(100) UNIQUE'
                            )
                except Exception:
                    # Column might already exist - that's OK
                    pass
    except Exception:
        # Database connection failed at startup - that's OK for serverless
        # The app will still start, and database operations will fail gracefully
        pass


# ============== DATABASE MODELS ==============

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=True)  # kept for legacy rows only
    email = db.Column(db.String(80), unique=True, nullable=False)
    supabase_id = db.Column(db.String(100), unique=True, nullable=True)
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

    def __init__(self, username, email, supabase_id):
        self.username = username
        self.email = email
        self.supabase_id = supabase_id

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


class CommonFood(db.Model):
    __tablename__ = 'common_foods'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_simple = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(100), default='Generic')
    serving_size = db.Column(db.String(50), default='100g')
    calories = db.Column(db.Float, default=0)
    protein = db.Column(db.Float, default=0)
    carbs = db.Column(db.Float, default=0)
    fat = db.Column(db.Float, default=0)
    fiber = db.Column(db.Float, default=0)
    sugar = db.Column(db.Float, default=0)
    sodium = db.Column(db.Float, default=0)


class FoodCache(db.Model):
    __tablename__ = 'food_cache'
    id = db.Column(db.Integer, primary_key=True)
    query_key = db.Column(db.String(200), nullable=False, unique=True, index=True)
    results_json = db.Column(db.Text, nullable=False)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# Initialize database schema (must come after all models are defined)
init_db()


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
        email = request.form['email']
        password = request.form['password']

        try:
            auth_resp = get_supabase().auth.sign_in_with_password({"email": email, "password": password})
            if not auth_resp or not auth_resp.user:
                raise Exception("Authentication failed")
            supabase_uid = auth_resp.user.id
        except Exception as e:
            print(f"Supabase auth error: {str(e)}")
            flash(f"Login failed: {str(e)}", "error")
            return render_template("login.html")

        user = User.query.filter_by(supabase_id=supabase_uid).first()
        if not user:
            flash("Account not found. Please register.", "error")
            return render_template("login.html")

        session.permanent = True
        session["user_id"] = user.id
        session["username"] = user.username
        flash("Welcome back, " + user.username + "!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
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

        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return render_template("register.html")

        try:
            auth_resp = get_supabase().auth.sign_up({"email": email, "password": password})
            if not auth_resp or not auth_resp.user:
                flash("Registration failed. Please try again.", "error")
                return render_template("register.html")
            supabase_uid = auth_resp.user.id
        except Exception as e:
            msg = str(e).lower()
            if "already" in msg or "registered" in msg:
                flash("Email already registered.", "error")
            else:
                flash("Registration error: " + str(e), "error")
            return render_template("register.html")

        new_user = User(username=username, email=email, supabase_id=supabase_uid)
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
    """Local-first search: CommonFood > Cache > FatSecret API > USDA fallback"""
    from food_apis import search_fatsecret, search_usda
    import json

    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'products': []})

    query_key = query.lower().strip()
    all_products = []
    cache_miss = True

    # Step 1: CommonFood table (instant, no API)
    common_hits = CommonFood.query.filter(
        CommonFood.name_simple.ilike(f'%{query_key}%')
    ).limit(10).all()

    for food in common_hits:
        all_products.append({
            'name': food.name,
            'brand': food.brand,
            'barcode': '',
            'image': '',
            'serving_size': food.serving_size,
            'calories': food.calories,
            'protein': food.protein,
            'carbs': food.carbs,
            'fat': food.fat,
            'fiber': food.fiber,
            'sugar': food.sugar,
            'sodium': food.sodium,
            '_source': 'common',
        })

    # Step 2: FoodCache lookup (TTL 7 days)
    CACHE_TTL_DAYS = 7
    cached = FoodCache.query.filter_by(query_key=query_key).first()
    if cached:
        age = datetime.utcnow() - cached.fetched_at
        if age.days < CACHE_TTL_DAYS:
            cached_products = json.loads(cached.results_json)
            all_products.extend(cached_products)
            cache_miss = False

    # Steps 3 & 4: API calls only on cache miss
    if cache_miss:
        api_products = []

        # FatSecret (primary — 5000 calls/day free)
        fs_results = search_fatsecret(query)
        api_products.extend(fs_results)

        # USDA fallback
        if not fs_results:
            usda_results = search_usda(query)
            api_products.extend(usda_results)

        # Save to cache (upsert pattern)
        if api_products:
            clean = [{k: v for k, v in p.items() if not k.startswith('_')}
                     for p in api_products]
            if cached:
                cached.results_json = json.dumps(clean)
                cached.fetched_at = datetime.utcnow()
            else:
                db.session.add(FoodCache(
                    query_key=query_key,
                    results_json=json.dumps(clean),
                ))
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        all_products.extend(api_products)

    # Merge and deduplicate
    SOURCE_PRIORITY = {'common': 0, 'fatsecret': 1, 'usda': 2, '': 1}
    seen = {}
    for p in all_products:
        key = (p['name'].lower()[:40], p['brand'].lower()[:20])
        if key not in seen:
            seen[key] = p
        else:
            existing_priority = SOURCE_PRIORITY.get(seen[key].get('_source', ''), 1)
            this_priority = SOURCE_PRIORITY.get(p.get('_source', ''), 1)
            if this_priority < existing_priority:
                seen[key] = p

    results = list(seen.values())
    results.sort(key=lambda p: (0 if p.get('_source') == 'common' else 1, len(p['name'])))

    for p in results:
        p.pop('_source', None)

    return jsonify({'products': results[:25]})


@app.route("/api/food/barcode/<barcode>")
@login_required
def api_food_barcode(barcode):
    """Look up food by barcode using USDA FoodData Central API"""
    from food_apis import search_usda

    try:
        results = search_usda(barcode)
        if results:
            product = results[0]
            return jsonify({
                'found': True,
                'product': product
            })
    except Exception as e:
        print(f"USDA barcode lookup error: {e}")

    return jsonify({'found': False, 'message': 'Product not found'})


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
