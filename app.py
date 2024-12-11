from flask import Flask, render_template, request, jsonify
import numpy as np
from scipy.optimize import linprog
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost/feed_ration_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Models
class FeedIngredient(db.Model):
    __tablename__ = 'feed_ingredients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    protein = db.Column(db.Float, nullable=False)
    fiber = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)


class NutrientRequirement(db.Model):
    __tablename__ = 'nutrient_requirements'
    id = db.Column(db.Integer, primary_key=True)
    animal_type = db.Column(db.String(50), nullable=False)
    protein = db.Column(db.Float, nullable=False)
    fiber = db.Column(db.Float, nullable=False)

# Helper function to calculate activity factor
def activity_factor(activity):
    activity_mapping = {
        'low': 0.1,
        'moderate': 0.25,
        'high': 0.5
    }
    return activity_mapping.get(activity.lower(), 0)

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/initialize-db')
def initialize_db():
    """Create tables if they do not exist."""
    with app.app_context():
        db.create_all()
    return "Database initialized successfully!"

@app.route('/populate')
def populate_data():
    """Populate the database with initial data."""
    with app.app_context():
        if not FeedIngredient.query.first():
            # Add feed ingredients
            feeds = [
                FeedIngredient(name="Corn", protein=7.5, fiber=10.0, cost=70),
                FeedIngredient(name="Soybean Meal", protein=48.0, fiber=6.0, cost=180),
                FeedIngredient(name="Wheat Bran", protein=18.0, fiber=44.0, cost=45),
            ]
            db.session.add_all(feeds)

        if not NutrientRequirement.query.first():
            # Add nutrient requirements
            requirements = [
                NutrientRequirement(animal_type="cattle", protein=700, fiber=3000),
                NutrientRequirement(animal_type="poultry", protein=170, fiber=30),
                NutrientRequirement(animal_type="goat", protein=350, fiber=400),
            ]
            db.session.add_all(requirements)
        
        db.session.commit()
    return "Database populated successfully!"

@app.route('/animal-requirements', methods=['GET', 'POST'])
def animal_requirements():
    if request.method == 'POST':
        # For JSON data, use request.get_json() to get the payload
        data = request.get_json()

        # Extract the animal_type, weight, and activity from the data
        animal_type = data.get('animal_type')
        weight = float(data.get('weight', 0))
        activity = data.get('activity')

        # Validate the animal_type (Ensure it's valid)
        valid_animal_types = ['cattle', 'poultry', 'goat']
        if animal_type not in valid_animal_types:
            return jsonify({"error": "Invalid animal type"}), 400

        # Fetch base requirements from the database
        base_requirements = NutrientRequirement.query.filter_by(animal_type=animal_type).first()

        # Check if the base requirements are found
        if not base_requirements:
            return jsonify({"error": "Animal type not found in database"}), 404

        # Calculate nutrient requirements
        protein = base_requirements.protein * (weight / 500) * (1 + activity_factor(activity))
        fiber = base_requirements.fiber * (weight / 500) * (1 + activity_factor(activity))

        # Return the calculated nutrient requirements as a response
        return jsonify({"protein": round(protein, 2), "fiber": round(fiber, 2)})

    # For GET request, render the animal requirements page
    return render_template('animal_requirements.html')


@app.route('/feed-options', methods=['GET', 'POST'])
def feed_options():
    if request.method == 'POST':
        # Handle updates to feed ingredient prices
        data = request.get_json()
        try:
            for name, price in data.items():
                feed = FeedIngredient.query.filter_by(name=name).first()
                if feed:
                    feed.cost = float(price)
            db.session.commit()
            return jsonify({"success": True, "message": "Prices updated successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400

    # For GET requests, render the feed options page
    feed_ingredients = FeedIngredient.query.all()
    return render_template('feed_options.html', feed_ingredients=feed_ingredients)


@app.route('/cost', methods=['POST', 'GET'])
def cost_estimation():
    if request.method == 'POST':
        try:
            # Get the updated prices and nutrient requirements from the request
            data = request.get_json()

            # Extract nutrient requirements and updated prices from the JSON data
            protein_requirement = float(data['protein'])
            fiber_requirement = float(data['fiber'])
            updated_prices = data['prices']

            # Fetch feed ingredients from the database
            feed_ingredients = FeedIngredient.query.all()

            # Prepare cost vector, protein values, and fiber values for the linear programming model
            costs = [float(updated_prices.get(feed.name, feed.cost)) for feed in feed_ingredients]
            protein_values = [feed.protein for feed in feed_ingredients]
            fiber_values = [feed.fiber for feed in feed_ingredients]

            # Linear programming setup
            A = [[-p for p in protein_values], [-f for f in fiber_values]]
            b = [-protein_requirement, -fiber_requirement]
            bounds = [(0, None) for _ in feed_ingredients]

            # Solve optimization
            result = linprog(c=costs, A_ub=A, b_ub=b, bounds=bounds, method="highs")

            if result.success:
                # If the optimization was successful, return quantities and total cost
                quantities = {feed.name: round(qty, 2) for feed, qty in zip(feed_ingredients, result.x)}
                total_cost = round(result.fun, 2)
                return jsonify({"success": True, "quantities": quantities, "total_cost": total_cost})
            else:
                # If optimization fails, return an error message
                return jsonify({"success": False, "message": "Unable to calculate cost. Try adjusting requirements."}), 400

        except Exception as e:
            # Handle exceptions (like missing data or invalid input)
            return jsonify({"success": False, "message": str(e)}), 400

    # Pass feed_ingredients to the template in the GET request
    feed_ingredients = FeedIngredient.query.all()
    return render_template('cost_estimation.html', feed_ingredients=feed_ingredients)

if __name__ == '__main__':
    app.run(debug=True)








'''
app = Flask(__name__)

# Updated feed ingredients for cattle
feed_ingredients = [
    {"name": "Corn", "protein": 7.5, "fiber": 10.0, "cost": 70},
    {"name": "Soybean Meal", "protein": 48.0, "fiber": 6.0, "cost": 180},
    {"name": "Wheat Bran", "protein": 18.0, "fiber": 44.0, "cost": 45},
]

# Updated nutrient requirements
nutrient_requirements = {
    "cattle": {"protein": 700, "fiber": 3000},
    "poultry": {"protein": 170, "fiber": 30},
    "goat": {"protein": 350, "fiber": 400},
}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/animal-requirements', methods=['GET', 'POST'])
def animal_requirements():
    if request.method == 'POST':
        animal_type = request.form.get('animal-type')
        weight = float(request.form.get('weight', 0))
        age = float(request.form.get('age', 0))
        activity = request.form.get('activity')

        # Adjust nutrient requirements based on weight, age, and activity
        base_requirements = nutrient_requirements.get(animal_type, {})
        protein = base_requirements.get("protein", 0) * (weight / 500) * (1 + activity_factor(activity))
        fiber = base_requirements.get("fiber", 0) * (weight / 500) * (1 + activity_factor(activity))

        return jsonify({"protein": round(protein, 2), "fiber": round(fiber, 2)})

    return render_template('animal_requirements.html')

def activity_factor(activity_level):
    """Returns a multiplier based on activity level."""
    factors = {"low": 0.1, "medium": 0.2, "high": 0.3}
    return factors.get(activity_level, 0)

@app.route('/feed-options', methods=['GET'])
def feed_options():
    return render_template('feed_options.html', feed_ingredients=feed_ingredients)

@app.route('/cost', methods=['POST'])
def cost_estimation():
    # Get the updated prices and nutrient requirements from the request
    data = request.get_json()

    # Extract nutrient requirements and updated prices from the request
    protein_requirement = float(data['protein'])
    fiber_requirement = float(data['fiber'])
    updated_prices = data['prices']

    # Define the feed ingredients with updated prices
    feed_ingredients = [
        {"name": "Corn", "protein": 7.5, "fiber": 10.0, "cost": float(updated_prices.get("Corn", 70.0))},
        {"name": "Soybean Meal", "protein": 48.0, "fiber": 6.0, "cost": float(updated_prices.get("Soybean Meal", 180.0))},
        {"name": "Wheat Bran", "protein": 18.0, "fiber": 44.0, "cost": float(updated_prices.get("Wheat Bran", 45.0))},
    ]

    # Prepare the cost vector, protein values, and fiber values for the linear programming model
    costs = [ingredient["cost"] for ingredient in feed_ingredients]
    protein_values = [ingredient["protein"] for ingredient in feed_ingredients]
    fiber_values = [ingredient["fiber"] for ingredient in feed_ingredients]

    # Constraints: Protein and fiber must meet or exceed requirements
    A = [
        [-val for val in protein_values],  # Protein constraint (negative for 'greater than or equal to' condition)
        [-val for val in fiber_values],    # Fiber constraint (negative for 'greater than or equal to' condition)
    ]
    b = [-protein_requirement, -fiber_requirement]  # Right-hand side of the constraints

    # Adding minimum constraints for Corn and Soybean Meal
    A.extend([
        [1, 0, 0],  # Corn minimum constraint
        [0, 1, 0],  # Soybean Meal minimum constraint
    ])
    b.extend([10, 5])  # Minimum quantities in kg

    # Bounds: Quantities of each ingredient must be non-negative (no less than 0)
    bounds = [(0, None) for _ in feed_ingredients]

    # Solve the linear programming problem
    result = linprog(c=costs, A_ub=A, b_ub=b, bounds=bounds, method="highs")

    # Debugging output to understand optimization
    print("Optimization result:", result)
    print("Protein requirements:", protein_requirement)
    print("Fiber requirements:", fiber_requirement)
    print("Feed costs:", costs)
    print("Protein values:", protein_values)
    print("Fiber values:", fiber_values)

    # Check if the optimization was successful
    if result.success:
        # Create a dictionary of ingredient quantities
        quantities = {feed_ingredients[i]["name"]: round(qty, 2) for i, qty in enumerate(result.x)}
        total_cost = round(result.fun, 2)  # Total cost of the feed ration
        return jsonify({"success": True, "quantities": quantities, "total_cost": total_cost})

    return jsonify({"success": False, "message": "Unable to calculate cost. Try adjusting requirements."})'''

if __name__ == '__main__':
    app.run(debug=True)
