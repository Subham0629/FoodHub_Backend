import json
import pytest
from app import app

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_get_menu(client):
    response = client.get('/menu')
    assert response.status_code ==  200
    assert isinstance(response.json, list)

def test_add_dish(client):
    dish_data = {
        "dish_name": "Chicken Curry",
        "price": 12.99,
        "availability": True
    }
    response = client.post('/add_dish', json=dish_data)
    assert response.status_code == 200
    assert response.json['message'] == 'Dish added successfully!'
    assert 'dish' in response.json

def test_remove_dish(client):
    response = client.delete('/remove_dish/dish123')
    assert response.status_code == 200
    assert response.json['message'] == 'Dish removed successfully!'

def test_new_order(client):
    order_data = {
        "customer_name": "John Doe",
        "dish_ids": ["dish123", "dish456"],
        "quantity": 2
    }
    response = client.post('/new_order', json=order_data)
    assert response.status_code == 200
    assert response.json['message'] == 'Invalid dish ID or dish not available!'
    assert 'order_id' not in response.json


def test_review_orders(client):
    response = client.get('/review_orders')
    assert response.status_code == 200
    assert isinstance(response.json, list)

def test_update_rating_review(client):
    rating_review_data = {
        "rating": 4.5,
        "reviews": "Great dish!"
    }
    response = client.patch('/update_rating_review/dish123', json=rating_review_data)
    assert response.status_code == 200
    assert response.json['message'] == 'Rating and review updated successfully!'

def test_update_availability(client):
    availability_data = {
        "availability": True
    }
    response = client.patch('/update_availability/dish123', json=availability_data)
    assert response.status_code == 200
    assert response.json['message'] == 'Availability updated successfully!'

def test_chatbot(client):
    message_data = {
        "message": "What are your operation hours?"
    }
    response = client.post('/chatbot', json=message_data)
    assert response.status_code == 200
    assert 'response' in response.json


