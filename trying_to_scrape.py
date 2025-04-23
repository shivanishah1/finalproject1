import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
import json
import re

# ======= CONFIG =======

# Recipe URLs to scrape
urls = [
    'https://joyfoodsunshine.com/the-most-amazing-chocolate-chip-cookies/',
    'https://pinchofyum.com/the-best-soft-chocolate-chip-cookies',
    'https://www.allrecipes.com/recipe/10909/annas-chocolate-chip-cookies/',
    'https://sallysbakingaddiction.com/chewy-chocolate-chip-cookies/',
    'https://preppykitchen.com/chewy-chocolate-chip-cookies/',
]

# Ingredient keywords you want to track as columns
ingredient_keywords = [
    "butter", "sugar", "brown sugar", "granulated sugar", "eggs", "egg", 
    "chocolate chips", "vanilla", "flour", "baking soda", "salt"
]

# ======= FUNCTIONS =======

def extract_ingredients_to_columns(ingredient_list):
    ingredients_dict = {key: "" for key in ingredient_keywords}

    for line in ingredient_list:
        line_clean = re.sub(r'\s+', ' ', line.strip().lower())
        for key in ingredient_keywords:
            if key in line_clean:
                ingredients_dict[key] += line_clean + "; "
                break
    return ingredients_dict

def parse_recipe(data, url):
    return {
        "Title": data.get("name"),
        "Ingredients (Raw)": ', '.join(data.get("recipeIngredient", [])),
        "Instructions": (
            ' '.join(
                step.get("text", "") for step in data.get("recipeInstructions", [])
                if isinstance(step, dict)
            ) if isinstance(data.get("recipeInstructions"), list)
            else data.get("recipeInstructions", "")
        ),
        "URL": url
    }

async def extract_recipe_async(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=30000)
            html = await page.content()
        except Exception as e:
            await browser.close()
            print(f"❌ Error loading {url}: {e}")
            return None
        await browser.close()

    soup = BeautifulSoup(html, "html.parser")

    # Try structured data first
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "Recipe":
                        parsed = parse_recipe(item, url)
                        ing_cols = extract_ingredients_to_columns(item.get("recipeIngredient", []))
                        return {**parsed, **ing_cols}
            elif data.get("@type") == "Recipe":
                parsed = parse_recipe(data, url)
                ing_cols = extract_ingredients_to_columns(data.get("recipeIngredient", []))
                return {**parsed, **ing_cols}
        except Exception:
            continue

    # Fallback to visible scraping
    try:
        title = soup.find('h1').get_text(strip=True)
        ingredients = [i.get_text(strip=True) for i in soup.select('[class*="ingredient"]')]
        instructions = [i.get_text(strip=True) for i in soup.select('[class*="instruction"], [class*="step"]')]

        parsed = {
            "Title": title,
            "Ingredients (Raw)": ', '.join(ingredients),
            "Instructions": ' '.join(instructions),
            "URL": url
        }
        ing_cols = extract_ingredients_to_columns(ingredients)
        return {**parsed, **ing_cols}
    except Exception as e:
        print(f"⚠️ No recipe schema or fallback found for: {url} → {e}")
        return None

# ======= MAIN =======

async def main():
    tasks = [extract_recipe_async(url) for url in urls]
    results = await asyncio.gather(*tasks)
    recipes = [r for r in results if r]

    if recipes:
        df = pd.DataFrame(recipes)
        df.to_excel("recipes.xlsx", index=False)
        print("✅ Saved to recipes.xlsx")
    else:
        print("🚫 No recipes were scraped.")

if __name__ == "__main__":
    asyncio.run(main())
