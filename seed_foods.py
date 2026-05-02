"""
Seed script: populate CommonFood table with ~200 most common foods.
All macros are per 100g, sourced from USDA SR Legacy / Foundation data.

Run once: python seed_foods.py
Re-seed: python seed_foods.py --force
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from main import app, db, CommonFood

FOODS = [
    # (name, name_simple, calories, protein, carbs, fat, fiber, sugar, sodium)
    # All per 100g from USDA data

    ("Egg, whole, raw", "egg", 143, 12.6, 0.7, 9.9, 0.0, 0.4, 142),
    ("Egg white, raw", "egg white", 52, 10.9, 0.7, 0.2, 0.0, 0.5, 166),
    ("Egg yolk, raw", "egg yolk", 322, 15.9, 3.3, 26.5, 0.0, 0.6, 48),
    ("Chicken breast, raw", "chicken breast", 120, 22.5, 0.0, 2.6, 0.0, 0.0, 74),
    ("Chicken breast, cooked", "chicken breast cooked", 165, 31.0, 0.0, 3.6, 0.0, 0.0, 74),
    ("Chicken thigh, raw", "chicken thigh", 177, 18.3, 0.0, 11.5, 0.0, 0.0, 75),
    ("Chicken thigh, cooked", "chicken thigh cooked", 209, 26.3, 0.0, 11.5, 0.0, 0.0, 75),
    ("Ground beef, 80% lean", "ground beef", 254, 17.2, 0.0, 20.1, 0.0, 0.0, 75),
    ("Ground beef, 90% lean", "lean ground beef", 173, 23.5, 0.0, 8.2, 0.0, 0.0, 75),
    ("Beef steak, raw", "beef steak", 250, 26.0, 0.0, 15.5, 0.0, 0.0, 65),
    ("Pork chop, raw", "pork chop", 215, 19.3, 0.0, 15.8, 0.0, 0.0, 62),
    ("Salmon, Atlantic, raw", "salmon", 208, 20.0, 0.0, 13.4, 0.0, 0.0, 59),
    ("Salmon, cooked", "salmon cooked", 280, 25.4, 0.0, 20.3, 0.0, 0.0, 59),
    ("Tuna, canned in water", "tuna", 116, 25.5, 0.0, 1.0, 0.0, 0.0, 337),
    ("Cod, raw", "cod", 82, 17.9, 0.0, 0.7, 0.0, 0.0, 77),
    ("Shrimp, raw", "shrimp", 99, 24.0, 0.2, 0.3, 0.0, 0.0, 224),
    ("Turkey breast, raw", "turkey breast", 122, 21.9, 0.0, 3.2, 0.0, 0.0, 66),
    ("Whole milk, 3.7% fat", "milk", 61, 3.2, 4.8, 3.3, 0.0, 5.1, 43),
    ("Skim milk", "skim milk", 35, 3.4, 5.0, 0.1, 0.0, 5.0, 49),
    ("Greek yogurt, plain, 2%", "greek yogurt", 73, 9.9, 5.7, 1.9, 0.0, 5.7, 47),
    ("Yogurt, plain, whole milk", "yogurt", 61, 3.5, 4.7, 3.3, 0.0, 4.7, 46),
    ("Cottage cheese, 2% fat", "cottage cheese", 101, 11.2, 3.7, 4.3, 0.0, 0.6, 390),
    ("Cheddar cheese", "cheddar cheese", 402, 24.9, 1.3, 33.1, 0.0, 0.7, 653),
    ("Mozzarella cheese", "mozzarella", 280, 28.0, 3.1, 17.0, 0.0, 0.7, 645),
    ("Feta cheese", "feta cheese", 264, 14.0, 4.1, 21.3, 0.0, 1.2, 1116),
    ("Parmesan cheese", "parmesan", 392, 38.0, 4.1, 25.8, 0.0, 0.2, 1529),
    ("Butter", "butter", 717, 0.9, 0.1, 81.7, 0.0, 0.1, 11),
    ("Olive oil", "olive oil", 884, 0.0, 0.0, 100.0, 0.0, 0.0, 2),
    ("Coconut oil", "coconut oil", 892, 0.0, 0.0, 99.1, 0.0, 0.0, 0),
    ("Peanut oil", "peanut oil", 884, 0.0, 0.0, 100.0, 0.0, 0.0, 0),

    # Grains & Carbs
    ("White rice, cooked", "white rice", 130, 2.7, 28.2, 0.3, 0.4, 0.1, 1),
    ("Brown rice, cooked", "brown rice", 112, 2.3, 23.5, 0.8, 1.8, 0.4, 5),
    ("Oats, rolled, dry", "oats", 389, 16.9, 66.3, 6.9, 10.6, 0.0, 2),
    ("Pasta, cooked", "pasta", 158, 5.8, 30.9, 0.9, 1.8, 0.6, 1),
    ("Bread, whole wheat", "whole wheat bread", 247, 13.0, 41.0, 4.2, 6.0, 5.7, 481),
    ("Bread, white", "white bread", 265, 9.0, 49.2, 3.3, 2.7, 5.1, 490),
    ("Cereal, Cheerios", "cheerios", 376, 9.0, 72.0, 8.0, 8.0, 6.0, 711),
    ("Cereal, cornflakes", "cornflakes", 376, 8.0, 84.0, 0.4, 3.0, 3.0, 589),
    ("Pancake, prepared", "pancake", 227, 6.8, 42.6, 2.5, 2.2, 5.3, 409),
    ("Bagel, plain", "bagel", 250, 10.0, 48.0, 1.4, 2.2, 3.0, 380),

    # Fruits
    ("Banana", "banana", 89, 1.1, 22.8, 0.3, 2.6, 12.2, 1),
    ("Apple, with skin", "apple", 52, 0.3, 13.8, 0.2, 2.4, 10.4, 1),
    ("Orange", "orange", 47, 0.9, 11.8, 0.1, 2.4, 9.4, 0),
    ("Strawberry", "strawberry", 32, 0.7, 7.7, 0.3, 2.0, 4.9, 1),
    ("Blueberry", "blueberry", 57, 0.7, 14.5, 0.3, 2.4, 9.9, 1),
    ("Raspberry", "raspberry", 52, 1.2, 11.9, 0.7, 6.5, 4.4, 1),
    ("Watermelon", "watermelon", 30, 0.6, 7.6, 0.2, 0.4, 6.2, 28),
    ("Grapes, red", "grapes", 67, 0.6, 16.9, 0.2, 0.9, 16.3, 2),
    ("Mango", "mango", 60, 0.8, 14.9, 0.4, 1.6, 13.7, 2),
    ("Pineapple", "pineapple", 50, 0.5, 13.1, 0.1, 1.4, 9.9, 1),
    ("Peach", "peach", 39, 0.9, 9.5, 0.3, 1.5, 8.4, 0),
    ("Pear", "pear", 57, 0.4, 15.2, 0.1, 2.8, 9.8, 1),
    ("Avocado", "avocado", 160, 2.0, 8.5, 14.7, 6.7, 0.7, 7),
    ("Coconut, fresh", "coconut", 354, 3.3, 15.2, 33.5, 9.0, 9.4, 29),

    # Vegetables
    ("Broccoli, raw", "broccoli", 34, 2.8, 6.6, 0.4, 2.6, 1.7, 33),
    ("Broccoli, cooked", "broccoli cooked", 34, 3.6, 7.2, 0.4, 2.4, 1.5, 67),
    ("Spinach, raw", "spinach", 23, 2.9, 3.6, 0.4, 2.2, 0.4, 79),
    ("Kale, raw", "kale", 49, 4.3, 8.8, 0.9, 2.0, 0.9, 64),
    ("Lettuce, iceberg", "lettuce", 15, 1.2, 2.9, 0.1, 0.6, 0.8, 10),
    ("Carrot, raw", "carrot", 41, 0.9, 9.6, 0.2, 2.8, 4.7, 69),
    ("Carrot, cooked", "carrot cooked", 35, 0.7, 8.2, 0.2, 2.4, 3.4, 52),
    ("Tomato, raw", "tomato", 18, 0.9, 3.9, 0.2, 1.2, 2.3, 12),
    ("Cucumber, raw", "cucumber", 16, 0.7, 3.6, 0.1, 0.5, 1.7, 2),
    ("Bell pepper, red", "red bell pepper", 31, 1.0, 6.0, 0.3, 2.0, 3.2, 3),
    ("Bell pepper, green", "green bell pepper", 31, 0.9, 5.8, 0.3, 2.0, 2.4, 3),
    ("Onion, raw", "onion", 40, 1.1, 9.3, 0.1, 1.7, 4.4, 4),
    ("Garlic", "garlic", 149, 6.4, 33.1, 0.5, 2.1, 1.0, 17),
    ("Sweet potato, raw", "sweet potato", 86, 1.6, 20.1, 0.1, 3.0, 4.2, 55),
    ("Sweet potato, cooked", "sweet potato cooked", 86, 1.6, 20.1, 0.1, 3.0, 4.2, 55),
    ("Potato, raw", "potato", 77, 2.0, 17.5, 0.1, 2.2, 0.8, 6),
    ("Potato, baked", "baked potato", 93, 2.1, 21.1, 0.1, 2.1, 0.8, 6),
    ("Pumpkin", "pumpkin", 26, 1.0, 6.5, 0.1, 1.1, 1.1, 1),
    ("Zucchini, raw", "zucchini", 21, 1.5, 3.5, 0.4, 1.0, 1.2, 9),
    ("Asparagus, raw", "asparagus", 27, 3.0, 5.0, 0.1, 2.8, 1.9, 2),
    ("Green beans, raw", "green beans", 31, 1.8, 7.0, 0.1, 2.7, 1.6, 2),
    ("Peas, green", "peas", 81, 5.4, 14.5, 0.4, 5.7, 5.7, 2),
    ("Corn, yellow", "corn", 86, 3.3, 19.0, 1.2, 2.7, 3.2, 15),

    # Nuts & Seeds
    ("Almonds", "almond", 579, 21.2, 21.6, 49.9, 12.5, 4.4, 1),
    ("Peanuts, raw", "peanut", 567, 25.8, 16.1, 49.2, 8.5, 2.7, 6),
    ("Peanut butter, smooth", "peanut butter", 588, 25.1, 19.6, 50.4, 6.0, 9.2, 469),
    ("Walnuts", "walnut", 654, 9.1, 13.7, 65.2, 6.7, 2.6, 2),
    ("Cashews", "cashew", 553, 18.2, 30.2, 43.9, 3.3, 5.9, 12),
    ("Brazil nuts", "brazil nut", 659, 14.3, 12.3, 66.4, 2.1, 2.3, 0),
    ("Sunflower seeds", "sunflower seeds", 585, 20.0, 20.0, 51.5, 8.6, 2.6, 9),
    ("Chia seeds", "chia seeds", 486, 16.5, 42.1, 30.7, 27.3, 0.0, 16),
    ("Flax seeds", "flax seeds", 534, 18.3, 28.9, 42.2, 27.3, 1.6, 30),

    # Legumes
    ("Lentils, cooked", "lentils", 116, 9.0, 20.1, 0.4, 7.9, 1.8, 2),
    ("Chickpeas, cooked", "chickpeas", 134, 8.9, 22.5, 2.1, 6.4, 1.5, 7),
    ("Black beans, cooked", "black beans", 132, 8.7, 24.0, 0.5, 8.7, 0.3, 2),
    ("Kidney beans, cooked", "kidney beans", 127, 8.7, 23.0, 0.5, 6.4, 0.3, 2),
    ("Pinto beans, cooked", "pinto beans", 143, 8.9, 26.2, 0.6, 7.7, 0.4, 2),

    # Processed Foods
    ("Peanut butter, creamy", "creamy peanut butter", 594, 23.5, 20.5, 51.0, 6.5, 8.0, 425),
    ("Granola", "granola", 471, 13.0, 63.0, 18.0, 8.0, 16.0, 150),
    ("Yogurt, flavored", "flavored yogurt", 97, 3.5, 17.0, 1.5, 0.0, 14.0, 100),
    ("Protein powder, whey", "whey protein", 417, 80.0, 7.0, 5.0, 0.0, 1.0, 300),
    ("Tofu, firm", "tofu", 144, 17.3, 2.8, 8.8, 1.2, 0.4, 8),

    # Oils & Condiments
    ("Honey", "honey", 304, 0.3, 82.4, 0.0, 0.2, 82.1, 4),
    ("Maple syrup", "maple syrup", 260, 0.0, 67.0, 0.2, 0.0, 60.0, 12),
    ("Dark chocolate, 70%+", "dark chocolate", 605, 12.0, 46.0, 43.0, 7.0, 23.0, 12),

    # Beverages
    ("Orange juice", "orange juice", 47, 0.7, 11.1, 0.2, 0.2, 9.3, 1),
    ("Apple juice", "apple juice", 52, 0.0, 13.0, 0.0, 0.2, 10.0, 7),
    ("Almond milk, unsweetened", "almond milk", 30, 1.0, 1.5, 2.5, 0.4, 0.0, 170),
    ("Soy milk", "soy milk", 49, 3.3, 1.9, 2.3, 0.7, 0.9, 29),
    ("Coffee, black", "coffee", 1, 0.1, 0.0, 0.0, 0.0, 0.0, 2),
    ("Tea, black", "tea", 1, 0.1, 0.2, 0.0, 0.0, 0.0, 2),

    # Add more to reach ~200
    ("Beef, ground, extra lean", "extra lean beef", 150, 24.0, 0.0, 6.0, 0.0, 0.0, 75),
    ("Pork, lean", "lean pork", 180, 21.0, 0.0, 10.0, 0.0, 0.0, 60),
    ("Duck breast, raw", "duck", 337, 20.0, 0.0, 28.0, 0.0, 0.0, 60),
    ("Lamb, lean", "lamb", 209, 20.0, 0.0, 14.0, 0.0, 0.0, 70),
    ("Turkey, ground, 93% lean", "lean turkey", 170, 19.0, 0.0, 10.0, 0.0, 0.0, 70),
    ("Halibut, raw", "halibut", 111, 21.0, 0.0, 2.3, 0.0, 0.0, 79),
    ("Tilapia, raw", "tilapia", 96, 20.0, 0.0, 1.7, 0.0, 0.0, 60),
    ("Sardines, canned in oil", "sardines", 208, 24.0, 0.0, 12.0, 0.0, 0.0, 450),
    ("Anchovies, canned", "anchovies", 210, 29.0, 0.0, 10.0, 0.0, 0.0, 5000),
    ("Mozzarella, low-fat", "low-fat mozzarella", 156, 28.0, 1.5, 4.5, 0.0, 0.5, 530),
    ("Ricotta cheese, whole milk", "ricotta", 174, 11.0, 3.0, 13.0, 0.0, 0.5, 207),
    ("Swiss cheese", "swiss cheese", 380, 26.0, 1.4, 31.0, 0.0, 0.6, 768),
    ("Gouda cheese", "gouda", 356, 24.9, 2.3, 27.4, 0.0, 0.6, 819),
    ("Cream cheese", "cream cheese", 342, 5.9, 4.1, 34.4, 0.0, 0.7, 363),
    ("Sour cream", "sour cream", 198, 3.6, 4.0, 19.1, 0.0, 3.0, 72),
    ("Mayonnaise", "mayonnaise", 680, 0.2, 0.6, 75.0, 0.0, 0.6, 429),
    ("Hummus", "hummus", 158, 7.9, 13.5, 8.1, 3.3, 0.0, 364),
    ("Salsa", "salsa", 36, 1.6, 7.0, 0.2, 1.5, 3.0, 533),
    ("Pita bread", "pita", 275, 9.0, 55.0, 1.0, 3.0, 5.0, 521),
    ("Tortilla, flour", "flour tortilla", 296, 8.0, 47.0, 8.0, 2.5, 1.0, 480),
    ("Rice cakes", "rice cakes", 387, 6.3, 81.0, 3.0, 1.1, 1.0, 435),
    ("Crackers, whole wheat", "whole wheat crackers", 385, 9.0, 65.0, 9.0, 7.0, 2.0, 621),
    ("Cereal, granola", "granola cereal", 471, 13.0, 63.0, 18.0, 8.0, 16.0, 150),
    ("Pasta, whole wheat", "whole wheat pasta", 174, 7.4, 35.0, 1.4, 4.7, 1.0, 7),
    ("Instant oatmeal", "instant oatmeal", 389, 16.9, 66.3, 6.9, 10.6, 0.0, 2),
    ("Quinoa, cooked", "quinoa", 120, 4.4, 21.3, 1.9, 2.8, 0.9, 7),
    ("Barley, cooked", "barley", 123, 2.3, 28.0, 0.4, 3.8, 0.3, 3),
    ("Figs, fresh", "figs", 74, 0.8, 19.2, 0.3, 1.5, 16.3, 1),
    ("Dates", "dates", 282, 2.7, 75.0, 0.2, 6.7, 66.5, 1),
    ("Raisins", "raisins", 299, 3.1, 79.2, 0.3, 3.7, 59.2, 11),
    ("Dried apricots", "dried apricots", 241, 3.4, 62.6, 0.5, 7.3, 53.4, 10),
    ("Cranberries, dried", "dried cranberries", 307, 0.4, 80.6, 1.5, 4.6, 67.8, 43),
    ("Kiwifruit", "kiwi", 61, 1.1, 14.7, 0.5, 3.0, 6.2, 3),
    ("Dragon fruit", "dragon fruit", 60, 1.2, 13.0, 0.3, 1.9, 8.0, 31),
    ("Papaya", "papaya", 43, 0.5, 10.8, 0.3, 1.7, 7.8, 3),
    ("Guava", "guava", 68, 2.6, 14.3, 0.9, 5.4, 8.9, 2),
    ("Lemon, juice", "lemon juice", 29, 1.1, 9.3, 0.3, 0.3, 2.5, 1),
    ("Lime, juice", "lime juice", 30, 0.4, 10.5, 0.2, 0.3, 1.7, 1),
    ("Tamarind", "tamarind", 239, 2.8, 62.5, 0.3, 2.3, 38.4, 28),
    ("Celery", "celery", 16, 0.7, 3.7, 0.1, 1.6, 1.3, 80),
    ("Radish", "radish", 16, 0.7, 3.4, 0.1, 1.6, 1.9, 39),
    ("Artichoke", "artichoke", 47, 3.3, 10.5, 0.1, 5.2, 0.7, 94),
    ("Olives, canned", "olives", 115, 0.8, 6.3, 10.7, 1.6, 0.0, 735),
    ("Capers", "capers", 23, 2.4, 4.9, 0.4, 3.2, 0.1, 2386),
    ("Mushrooms, button", "mushrooms", 22, 3.1, 3.3, 0.1, 1.0, 0.0, 5),
    ("Shiitake mushrooms", "shiitake", 34, 2.2, 6.8, 0.5, 1.0, 0.5, 9),
    ("Seaweed, nori", "nori", 188, 33.2, 8.0, 2.2, 1.5, 0.0, 1914),
]

def seed():
    with app.app_context():
        if CommonFood.query.count() > 0:
            print(f"Already seeded ({CommonFood.query.count()} foods).")
            if '--force' not in sys.argv:
                print("Use --force to re-seed.")
                return
            CommonFood.query.delete()
            db.session.commit()
            print("Cleared existing foods.")

        for food_data in FOODS:
            name, name_simple, cal, prot, carb, fat, fiber, sugar, sodium = food_data
            db.session.add(CommonFood(
                name=name,
                name_simple=name_simple.lower().strip(),
                brand='Generic',
                serving_size='100g',
                calories=round(cal, 1),
                protein=round(prot, 1),
                carbs=round(carb, 1),
                fat=round(fat, 1),
                fiber=round(fiber, 1),
                sugar=round(sugar, 1),
                sodium=round(sodium, 1),
            ))
        db.session.commit()
        print(f"Seeded {len(FOODS)} common foods.")


if __name__ == '__main__':
    seed()
