from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import requests
import openai
import json
import uuid
import os

app = Flask(__name__)
CORS(app)
load_dotenv()
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading', logger=True, engineio_logger=True, broadcast=True)
openai.api_key = os.environ.get("open_api_key")
# MongoDB connection
client = MongoClient(os.environ.get("mongoUrl"))
db = client['foodhub']  # Replace 'food_delivery' with your database name
menu_collection = db['menu']
order_collection = db['orders']

# Generate a unique order ID
def generate_order_id(order_data):
    if order_data:
        order_ids = [order['order_id'] for order in order_data]
        max_order_id = max(order_ids)
        return max_order_id + 1
    else:
        return 1

# Function to serialize MongoDB documents
def serialize_docs(docs):
    serialized_docs = []
    for doc in docs:
        doc['_id'] = str(doc['_id'])  # Convert ObjectId to string
        serialized_docs.append(doc)
    return serialized_docs

@app.route('/menu', methods=['GET'])
def get_menu():
    menu = menu_collection.find({})
    serialized_menu = serialize_docs(menu)
    return jsonify(serialized_menu)

@app.route('/add_dish', methods=['POST'])
def add_dish():
    dish = request.get_json()
    dish_name = dish.get('dish_name')
    price = dish.get('price')
    availability = dish.get('availability', False)

    if dish_name is None or price is None:
        return jsonify({'message': 'Dish name and price are required!'})

    # Generate a random menu ID using a combination of uuid and the counter
    menu_id = str(uuid.uuid4())

    new_dish = {
        'dish_id': menu_id,
        'dish_name': dish_name,
        'price': price,
        'availability': availability,
        'rating': [],
        'reviews': []
    }

    menu_collection.insert_one(new_dish)

    return jsonify({'message': 'Dish added successfully!', 'dish': new_dish})

@app.route('/remove_dish/<dish_id>', methods=['DELETE'])
def remove_dish(dish_id):
    menu_collection.delete_one({'dish_id': dish_id})

    return jsonify({'message': 'Dish removed successfully!'})

@app.route('/new_order', methods=['POST'])
def new_order():
    order = request.get_json()
    order_id = str(uuid.uuid4())

    dish_ids = order.get('dish_ids', [])
    for dish_id in dish_ids:
        dish = menu_collection.find_one({'dish_id': dish_id})
        if not dish or not dish.get('availability'):
            return jsonify({'message': 'Invalid dish ID or dish not available!'})

    new_order = {
        'order_id': order_id,
        'customer_name': order.get('customer_name'),
        'dish_ids': dish_ids,
        'quantity': order.get('quantity'),
        'status': 'received',
        'rating': [],
        'reviews': []
    }

    order_collection.insert_one(new_order)

    # Send a socket event to all connected clients with the updated order status
    socketio.emit('order_status_updated', {'order_id': order_id, 'status': 'received'}, namespace='/')
    
    return jsonify({'message': 'Order placed successfully!', 'order_id': order_id})

@app.route('/update_order_status/<order_id>', methods=['PATCH'])
def update_order_status(order_id):
    new_status = request.json.get('status')
    if not new_status:
        return jsonify({'message': 'Invalid status!'})
    
    order_collection.update_one({'order_id': order_id}, {'$set': {'status': new_status}})

    # Send a socket event to all connected clients with the updated order status
    socketio.emit('order_status_updated', {'order_id': order_id, 'status': new_status}, namespace='/')
    
    return jsonify({'message': 'Order status updated successfully!'})

@app.route('/review_orders', methods=['GET'])
def review_orders():
    orders = order_collection.find({})
    serialized_orders = serialize_docs(orders)
    return jsonify(serialized_orders)

@app.route('/update_rating_review/<dish_id>', methods=['PATCH'])
def update_rating_review(dish_id):
    new_rating = request.json.get('rating')
    new_review = request.json.get('reviews')

    if new_rating is None or new_review is None:
        return jsonify({'message': 'Invalid rating or review!'})

    menu_collection.update_one(
        {'dish_id': dish_id},
        {'$push': {'rating': new_rating, 'reviews': new_review}}
    )

    return jsonify({'message': 'Rating and review updated successfully!'})


@app.route('/update_availability/<dish_id>', methods=['PATCH'])
def update_availability(dish_id):
    availability = request.json.get('availability')
    menu_collection.update_one({'dish_id': dish_id}, {'$set': {'availability': availability}})

    return jsonify({'message': 'Availability updated successfully!'})

@app.route('/chatbot', methods=['POST'])
def chatbot():
    """
    Retrieves the chatbot's response for a user message.

    Returns:
        JSON response containing the chatbot's response.

    """
    request_data = request.get_json()
    user_message = request_data['message']

    # Get the chatbot's response for the user message
    chatbot_response = get_chatbot_response(user_message)

    # Return the response as JSON
    return jsonify({'response': chatbot_response})

def get_chatbot_response(message):
    prompt = f"Food Delivery Chatbot:\nUser: {message}\nChatbot:"
    payload = {
        'prompt': prompt,
        'max_tokens': 100,
    }
    
    headers = {
        'Authorization': f'Bearer {openai.api_key}',
        'Content-Type': 'application/json'
    }
    
    response = requests.post(
        'https://api.openai.com/v1/engines/text-davinci-003/completions',
        data=json.dumps(payload),
        headers=headers
    )
    
    if response.status_code == 200:
        chatbot_response = response.json()['choices'][0]['text'].strip()
        if 'operation hours' in message.lower():
            chatbot_response = "Our operation hours are from 9 AM to 6 PM."
        elif 'status of my order' in message.lower():
            chatbot_response = "Please provide your order ID, and we will check the status for you."
        elif 'popular dish' in message.lower():
            chatbot_response = "Our most popular dish is the Spicy Chicken Pasta."
        # Add more custom question keywords and corresponding responses
        elif 'delivery options' in message.lower():
            chatbot_response = "We offer multiple delivery options, including standard delivery and express delivery."
        elif 'payment methods' in message.lower():
            chatbot_response = "We accept various payment methods such as credit cards, debit cards, and digital wallets."
        elif 'menu' in message.lower():
            chatbot_response = "You can find our menu on our website or in the app. It includes a wide range of delicious dishes."
        # Add more custom question keywords and corresponding responses here
        else:
            chatbot_response = "I'm sorry, but I don't have the information you're looking for. Can I help you with anything else?"
        return chatbot_response
    else:
        return "Oops! Something went wrong with the chatbot."

@socketio.on('connect', namespace='/')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect', namespace='/')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)      
