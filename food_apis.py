"""
Food API integrations: FatSecret (primary) and USDA (fallback).
Handles OAuth2 token management for FatSecret and normalizes responses.
"""

import os
import time
import re
import requests
from datetime import datetime

FATSECRET_CLIENT_ID = os.environ.get('FATSECRET_CLIENT_ID', '')
FATSECRET_CLIENT_SECRET = os.environ.get('FATSECRET_CLIENT_SECRET', '')
USDA_API_KEY = os.environ.get('USDA_API_KEY', 'DEMO_KEY')

_fatsecret_token = {
    'access_token': None,
    'expires_at': 0.0,
}


def get_fatsecret_token() -> str | None:
    """Return a valid FatSecret Bearer token, refreshing if expired."""
    if not FATSECRET_CLIENT_ID or not FATSECRET_CLIENT_SECRET:
        return None

    now = time.time()
    if _fatsecret_token['access_token'] and now < _fatsecret_token['expires_at'] - 60:
        return _fatsecret_token['access_token']

    try:
        resp = requests.post(
            'https://oauth.fatsecret.com/connect/token',
            data={
                'grant_type': 'client_credentials',
                'scope': 'basic',
            },
            auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET),
            timeout=8,
        )
        if resp.status_code == 200:
            payload = resp.json()
            _fatsecret_token['access_token'] = payload['access_token']
            _fatsecret_token['expires_at'] = now + payload.get('expires_in', 86400) - 60
            return _fatsecret_token['access_token']
    except Exception as e:
        print(f"FatSecret token error: {e}")
    return None


def _parse_fatsecret_description(desc: str) -> dict:
    """Parse FatSecret food_description: 'Per 100g - Calories: 52kcal | Fat: 0.10g | ...'"""
    result = {'calories': 0, 'fat': 0, 'carbs': 0, 'protein': 0, 'fiber': 0, 'sugar': 0, 'sodium': 0}
    patterns = {
        'calories': r'Calories:\s*([\d.]+)',
        'fat': r'Fat:\s*([\d.]+)',
        'carbs': r'Carbs:\s*([\d.]+)',
        'protein': r'Protein:\s*([\d.]+)',
        'fiber': r'Fiber:\s*([\d.]+)',
        'sugar': r'Sugar:\s*([\d.]+)',
        'sodium': r'Sodium:\s*([\d.]+)',
    }
    for key, pat in patterns.items():
        m = re.search(pat, desc, re.IGNORECASE)
        if m:
            result[key] = round(float(m.group(1)), 1)
    return result


def search_fatsecret(query: str) -> list[dict]:
    """Call FatSecret foods.search, return normalized product dicts."""
    token = get_fatsecret_token()
    if not token:
        return []

    try:
        resp = requests.get(
            'https://platform.fatsecret.com/rest/server.api',
            headers={'Authorization': f'Bearer {token}'},
            params={
                'method': 'foods.search',
                'search_expression': query,
                'max_results': 10,
                'format': 'json',
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        foods = data.get('foods', {}).get('food', [])
        if isinstance(foods, dict):
            foods = [foods]

        results = []
        for food in foods:
            desc = food.get('food_description', '')
            macros = _parse_fatsecret_description(desc)
            results.append({
                'name': food.get('food_name', ''),
                'brand': food.get('brand_name', 'Generic') or 'Generic',
                'barcode': '',
                'image': '',
                'serving_size': '100g',
                'calories': macros.get('calories', 0),
                'protein': macros.get('protein', 0),
                'carbs': macros.get('carbs', 0),
                'fat': macros.get('fat', 0),
                'fiber': macros.get('fiber', 0),
                'sugar': macros.get('sugar', 0),
                'sodium': macros.get('sodium', 0),
                '_source': 'fatsecret',
            })
        return results
    except Exception as e:
        print(f"FatSecret search error: {e}")
        return []


def search_usda(query: str) -> list[dict]:
    """USDA FoodData Central search — returns normalized product dicts."""
    try:
        resp = requests.get(
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            params={
                'query': query,
                'pageSize': 15,
                'dataType': 'Foundation,SR Legacy,Survey (FNDDS),Branded',
                'api_key': USDA_API_KEY,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return []

        results = []
        for food in resp.json().get('foods', []):
            name = food.get('description', '')
            if not name or len(name) > 100:
                continue
            nutrients = {n['nutrientName']: n['value'] for n in food.get('foodNutrients', [])}
            data_type = food.get('dataType', '')
            brand = food.get('brandOwner', '') or food.get('brandName', '')

            if data_type in ('Foundation', 'SR Legacy'):
                brand = 'Generic'
            elif data_type == 'Survey (FNDDS)':
                brand = 'USDA Standard'
            elif not brand:
                brand = 'Branded'

            results.append({
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
                'sugar': nutrients.get('Sugars, total including NLEA',
                                      nutrients.get('Sugars, total', 0)) or 0,
                'sodium': nutrients.get('Sodium, Na', 0) or 0,
                '_source': 'usda',
            })
        return results
    except Exception as e:
        print(f"USDA search error: {e}")
        return []
